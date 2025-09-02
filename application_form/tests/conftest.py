import logging
import string
import uuid
from datetime import timedelta
from typing import Dict, List, Tuple, Union
from unittest.mock import Mock

from django.conf import settings
from django.utils import timezone
from elasticsearch.helpers.test import get_test_client
from elasticsearch_dsl.connections import add_connection
from factory.faker import faker
from pytest import fixture

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartments, get_project
from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form.api.serializers import ApplicationSerializer
from application_form.enums import (
    ApartmentReservationState,
    ApplicationArrivalMethod,
    ApplicationType,
)
from application_form.models import ApartmentReservation
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import (
    ApplicantFactory,
    ApplicationApartmentFactory,
)
from application_form.tests.utils import (
    calculate_ssn_suffix,
    get_elastic_apartments_uuids,
    get_for_sale_elastic_apartments,
)
from connections.tests.factories import ApartmentMinimalFactory
from users.tests.conftest import (  # noqa: F401
    api_client,
    drupal_salesperson_api_client,
    drupal_server_api_client,
    profile_api_client,
    sales_ui_salesperson_api_client,
    user_api_client,
)

faker.config.DEFAULT_LOCALE = "fi_FI"


_logger = logging.getLogger()


def setup_elasticsearch():
    test_client = get_test_client()
    add_connection("default", test_client)
    if test_client.indices.exists(index=settings.APARTMENT_INDEX_NAME):
        test_client.indices.delete(index=settings.APARTMENT_INDEX_NAME)
    test_client.indices.create(index=settings.APARTMENT_INDEX_NAME)
    return test_client


def teardown_elasticsearch(test_client):
    if test_client.indices.exists(index=settings.APARTMENT_INDEX_NAME):
        test_client.indices.delete(index=settings.APARTMENT_INDEX_NAME)


@fixture(scope="module")
def elasticsearch():
    test_client = setup_elasticsearch()
    yield test_client
    teardown_elasticsearch(test_client)


@fixture(scope="module")
def elastic_apartments(elasticsearch):
    yield ApartmentMinimalFactory.create_for_sale_batch(10)


@fixture
def check_latest_reservation_state_change_events():
    # makes sure the latest ApartmentReservationStateChangeEvent matches the latest
    # ApartmentReservation state for every ApartmentReservation
    # Note: a failure here will be reported as an error instead of a failed test
    yield
    for reservation in ApartmentReservation.objects.all():
        assert reservation.state_change_events.last().state == reservation.state


def generate_apartments(elasticsearch, apartment_count: int, apartment_kwargs: Dict):
    apartments = []
    apartments.append(ApartmentDocumentFactory(**apartment_kwargs))
    for _ in range(apartment_count):
        apartments.append(
            ApartmentDocumentFactory(
                project_uuid=apartments[0].project_uuid,
                **apartment_kwargs,
            )
        )

    return apartments


@fixture
def elastic_single_project_with_apartments(elasticsearch):
    application_end_time = timezone.now() + timedelta(days=10)
    apartments = generate_apartments(
        elasticsearch,
        10,
        {
            "apartment_state_of_sale": "FOR_SALE",
            "_language": "fi",
            "project_application_end_time": application_end_time,
        },
    )
    yield apartments

    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_project_with_5_apartments(elasticsearch):
    apartments = next(elastic_project_with_n_apartments(elasticsearch, 5))
    yield apartments[0].project_uuid, apartments


@fixture
def elastic_project_with_24_apartments(elasticsearch):
    """
    24 apartments, A, B, C, D staircases, apartment numbers from A1-F4
    """
    apartments = next(elastic_project_with_n_apartments(elasticsearch, 24))

    apartments_in_staircase = 4
    letter_index = 0
    apartment_number = 0
    for idx, apartment in enumerate(apartments):
        apartment_number += 1

        if idx > 0 and idx % apartments_in_staircase == 0:
            letter_index += 1
            apartment_number = 1

        staircase_letter = string.ascii_uppercase[letter_index]

        apartment.apartment_number = f"{staircase_letter}{apartment_number}"
        pass

    yield apartments[0].project_uuid, apartments


# @fixture
def elastic_project_with_n_apartments(elasticsearch, apartment_count: int):
    """
    Parametrizable to get more/less test apartments
    """
    apartments = []

    apartment = ApartmentDocumentFactory()

    apartments_in_staircase = 4
    letter_index = 0
    apartment_index = 0
    for idx in range(apartment_count):

        apartment_index += 1

        staircase_letter = string.ascii_uppercase[letter_index]
        apartment_number = f"{staircase_letter}{apartment_index}"

        apartments.append(
            ApartmentDocumentFactory(
                project_uuid=apartment.project_uuid, apartment_number=apartment_number
            )
        )

        if idx > 0 and idx % apartments_in_staircase == 0:
            letter_index += 1
            apartment_index = 0

    yield apartments

    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_hitas_project_with_5_apartments(elasticsearch):
    apartments = []

    apartment = ApartmentDocumentFactory(project_ownership_type="Hitas")
    apartments.append(apartment)

    for _ in range(4):
        apartments.append(
            ApartmentDocumentFactory(
                project_uuid=apartment.project_uuid, project_ownership_type="Hitas"
            )
        )
    yield apartment.project_uuid, apartments

    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_hitas_project_with_tiny_and_big_apartment(elasticsearch):
    tiny_apartment = ApartmentDocumentFactory(
        project_ownership_type="Hitas", room_count=1
    )
    big_apartment = ApartmentDocumentFactory(
        project_uuid=tiny_apartment.project_uuid,
        project_ownership_type="Hitas",
        room_count=10,
    )
    yield tiny_apartment.project_uuid, tiny_apartment, big_apartment

    tiny_apartment.delete(refresh=True)
    big_apartment.delete(refresh=True)


@fixture
def elastic_hitas_project_with_3_tiny_apartments(elasticsearch):
    apartments = []

    apartment = ApartmentDocumentFactory(project_ownership_type="Hitas", room_count=1)
    apartments.append(apartment)

    for _ in range(2):
        apartments.append(
            ApartmentDocumentFactory(
                project_uuid=apartment.project_uuid,
                project_ownership_type="Hitas",
                room_count=1,
            )
        )
    yield apartment.project_uuid, apartments

    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_hitas_project_with_apartment_room_count_2(elasticsearch):
    apartment = ApartmentDocumentFactory(project_ownership_type="Hitas", room_count=2)

    yield apartment.project_uuid, apartment

    apartment.delete(refresh=True)


@fixture
def elastic_hitas_project_with_apartment_room_count_10(elasticsearch):
    apartment = ApartmentDocumentFactory(project_ownership_type="Hitas", room_count=10)

    yield apartment.project_uuid, apartment

    apartment.delete(refresh=True)


@fixture
def elastic_haso_project_with_5_apartments(elasticsearch):
    apartments = []

    apartment = ApartmentDocumentFactory(project_ownership_type="Haso")
    apartments.append(apartment)

    for _ in range(4):
        apartments.append(
            ApartmentDocumentFactory(
                project_uuid=apartment.project_uuid, project_ownership_type="Haso"
            )
        )
    yield apartment.project_uuid, apartments

    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_project_application_time_active():
    apartment = ApartmentDocumentFactory(
        project_application_end_time=timezone.now() + timedelta(days=1)
    )
    yield apartment.project_uuid, apartment
    apartment.delete(refresh=True)


@fixture
def elastic_hitas_project_application_end_time_finished(elasticsearch):
    apartment = ApartmentDocumentFactory(
        project_ownership_type="Hitas",
        project_application_end_time=timezone.now() - timedelta(days=1),
    )
    yield apartment.project_uuid, apartment
    apartment.delete(refresh=True)


@fixture
def elastic_haso_project_application_end_time_finished(elasticsearch):
    apartment = ApartmentDocumentFactory(
        project_ownership_type="Haso",
        project_application_end_time=timezone.now() - timedelta(days=1),
    )
    yield apartment.project_uuid, apartment
    apartment.delete(refresh=True)


def sell_apartments(
    project_uuid: str, sell_count: int
) -> Tuple[ApartmentDocument, List[ApartmentDocument]]:
    """Sets the state of apartments in the given project to SOLD and creates
    the necessary ApartmentReservationStateChangeEvent objects into test db.

    Args:
        project_uuid (str): The project UUID
        sell_count (int): How many apartments to sell

    Returns:
        Tuple of the given project and apartments

    Throws:
        ValueError: If sell_count is higher than the amount of apartments
    """
    project = get_project(project_uuid)
    apartments = get_apartments(project.project_uuid, True)
    if sell_count > len(apartments):
        raise ValueError(
            f"sell_count is larger than the list of apartments on the project ({sell_count} > {len(apartments)})"  # noqa: E501
        )

    for apartment in apartments:
        apt_app = ApplicationApartmentFactory.create_batch(
            2, apartment_uuid=apartment.uuid
        )
        add_application_to_queues(apt_app[0].application)
        add_application_to_queues(apt_app[1].application)
    distribute_apartments(project.project_uuid)

    for i, apartment in enumerate(apartments):
        if i <= (sell_count - 1):

            reservation = (
                ApartmentReservation.objects.filter(apartment_uuid=apartment.uuid)
                .reserved()
                .first()
            )
            reservation.set_state(ApartmentReservationState.SOLD)

    return (project, apartments)


@fixture
def elastic_hitas_project_with_4_sold_apartments(
    elastic_hitas_project_with_5_apartments,
):
    hitas_project, hitas_apartments = sell_apartments(
        elastic_hitas_project_with_5_apartments[0], 4
    )
    yield hitas_project, hitas_apartments


@fixture
def elastic_haso_project_with_4_sold_apartments(elastic_haso_project_with_5_apartments):
    project, apartments = elastic_haso_project_with_5_apartments
    yield project, apartments


def create_application_data(
    profile,
    application_type=ApplicationType.HASO,
    num_applicants=2,
    apartments: Union[List[ApartmentDocument], None] = None,
):
    # Fetch apartments if needed
    if not apartments:
        apartments = get_for_sale_elastic_apartments()

    project_uuid, apartment_uuids = get_elastic_apartments_uuids(apartments)

    apartments_data = [
        {"priority": index, "identifier": apartment_uuid}
        for index, apartment_uuid in enumerate(apartment_uuids[0:5])
    ]
    right_of_residence = 123456 if application_type == ApplicationType.HASO else None
    # Build application request data
    application_data = {
        "application_uuid": str(uuid.uuid4()),
        "application_type": application_type.value,
        "has_children": True,
        "right_of_residence": right_of_residence,
        "additional_applicant": None,
        "applicant": {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "email": profile.email,
            "street_address": profile.street_address,
            "postal_code": profile.postal_code,
            "city": profile.city,
            "phone_number": profile.phone_number,
            "date_of_birth": profile.date_of_birth,
            "ssn_suffix": profile.ssn_suffix,
        },
        "project_id": str(project_uuid),
        "apartments": apartments_data,
        "has_hitas_ownership": True,
        "is_right_of_occupancy_housing_changer": True,
    }
    # Add a second applicant if needed
    if num_applicants == 2:
        date_of_birth = faker.Faker().date_of_birth(minimum_age=18)
        additional_applicant = ApplicantFactory.build()
        application_data["additional_applicant"] = {
            "first_name": additional_applicant.first_name,
            "last_name": additional_applicant.last_name,
            "email": additional_applicant.email,
            "street_address": additional_applicant.street_address,
            "postal_code": additional_applicant.postal_code,
            "city": additional_applicant.city,
            "phone_number": additional_applicant.phone_number,
            "date_of_birth": f"{date_of_birth:%Y-%m-%d}",
            "ssn_suffix": calculate_ssn_suffix(date_of_birth),
        }
    return application_data


def create_validated_application_data(
    profile, application_type=ApplicationType.HASO, num_applicants=2
):
    application_data = create_application_data(
        profile, application_type, num_applicants
    )
    serializer = ApplicationSerializer(
        data=application_data,
        context={"request": Mock(user=profile.user)},
    )
    serializer.is_valid(raise_exception=True)
    return {**serializer.validated_data, "profile": profile}


def prepare_metadata(data, profile):
    process_number = (
        METADATA_HASO_PROCESS_NUMBER
        if data["type"] == ApplicationType.HASO
        else METADATA_HITAS_PROCESS_NUMBER
    )
    data.update(
        {
            "handler_information": METADATA_HANDLER_INFORMATION,
            "process_number": process_number,
            "method_of_arrival": ApplicationArrivalMethod.ELECTRONICAL_SYSTEM.value,
            "sender_names": profile.full_name,
        }
    )
    return data
