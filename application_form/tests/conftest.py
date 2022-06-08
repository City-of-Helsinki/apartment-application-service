import faker.config
import uuid
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from elasticsearch.helpers.test import get_test_client
from elasticsearch_dsl.connections import add_connection
from factory.faker import faker
from pytest import fixture
from unittest.mock import Mock

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.api.serializers import ApplicationSerializer
from application_form.enums import ApplicationType
from application_form.models import ApartmentReservation
from application_form.tests.factories import ApplicantFactory
from application_form.tests.utils import (
    calculate_ssn_suffix,
    get_elastic_apartments_uuids,
)
from connections.tests.factories import ApartmentMinimalFactory
from users.tests.conftest import (  # noqa: F401
    api_client,
    profile_api_client,
    salesperson_api_client,
)

faker.config.DEFAULT_LOCALE = "fi_FI"


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


@fixture
def elastic_single_project_with_apartments(elasticsearch):
    apartments = []
    apartments.append(
        ApartmentMinimalFactory(
            apartment_state_of_sale="FOR_SALE",
            _language="fi",
        )
    )
    for _ in range(10):
        apartments.append(
            ApartmentMinimalFactory(
                apartment_state_of_sale="FOR_SALE",
                _language="fi",
                project_uuid=apartments[0].project_uuid,
            )
        )
    yield apartments

    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_project_with_5_apartments(elasticsearch):
    apartments = []

    apartment = ApartmentDocumentFactory()
    apartments.append(apartment)

    for _ in range(4):
        apartments.append(ApartmentDocumentFactory(project_uuid=apartment.project_uuid))
    yield apartment.project_uuid, apartments

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


def create_application_data(
    profile, application_type=ApplicationType.HASO, num_applicants=2
):
    # Build apartments
    project_uuid, apartment_uuids = get_elastic_apartments_uuids()
    apartments_data = [
        {"priority": index, "identifier": apartment_uuid}
        for index, apartment_uuid in enumerate(apartment_uuids[0:5])
    ]
    right_of_residence = 123456 if application_type == ApplicationType.HASO else None

    # Build application request data
    application_data = {
        "application_uuid": str(uuid.uuid4()),
        "application_type": application_type.value,
        "ssn_suffix": profile.ssn_suffix,
        "has_children": True,
        "right_of_residence": right_of_residence,
        "additional_applicant": None,
        "project_id": str(project_uuid),
        "apartments": apartments_data,
        "has_hitas_ownership": True,
        "is_right_of_occupancy_housing_changer": True,
    }
    # Add a second applicant if needed
    if num_applicants == 2:
        date_of_birth = faker.Faker().date_of_birth(minimum_age=18)
        applicant = ApplicantFactory.build()
        application_data["additional_applicant"] = {
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "email": applicant.email,
            "street_address": applicant.street_address,
            "postal_code": applicant.postal_code,
            "city": applicant.city,
            "phone_number": applicant.phone_number,
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
