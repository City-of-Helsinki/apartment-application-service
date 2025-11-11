from datetime import datetime, timedelta
from typing import List
from unittest.mock import MagicMock, patch

from application_form.services.queue import add_application_to_queues
import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status

from apartment.elastic.documents import ApartmentDocument
from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form import error_codes
from application_form.enums import (
    ApartmentReservationState,
    ApplicationArrivalMethod,
    ApplicationType,
)
from application_form.models import ApartmentReservation, Application
from application_form.tests.conftest import create_application_data, generate_apartments
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from audit_log.models import AuditLog
from connections.enums import ApartmentStateOfSale
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.models import Profile
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
def test_application_post(api_client, elastic_single_project_with_apartments):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201
    assert response.data == {"application_uuid": data["application_uuid"]}

    for reservation in ApartmentReservation.objects.all():
        assert reservation.state_change_events.last().user is None


@pytest.mark.django_db
def test_application_post_sets_nin(api_client, elastic_single_project_with_apartments):
    # Setup: Create application data with NIN and a profile without NIN
    profile: Profile
    profile = ProfileFactory()  # type: ignore
    data = create_application_data(profile)
    profile.national_identification_number = ""
    profile.save(update_fields=["national_identification_number"])
    assert profile.national_identification_number == ""
    assert not profile.ssn_suffix
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    # Run: Post the application data
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    # Check the response and side effects, NIN of profile should be set
    assert response.status_code == 201
    assert response.data == {"application_uuid": data["application_uuid"]}
    profile.refresh_from_db()
    assert profile.ssn_suffix == data["applicant"]["ssn_suffix"]
    assert len(profile.national_identification_number) == 11


@pytest.mark.parametrize("already_existing_customer", (False, True))
@pytest.mark.django_db
def test_application_post_single_profile_customer(
    api_client,
    elastic_single_project_with_apartments,
    already_existing_customer,
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    assert Profile.objects.count() == 1
    if already_existing_customer:
        apartment = ApartmentDocumentFactory()
        application = ApplicationFactory(
            customer=CustomerFactory(primary_profile=profile, has_children=True),
        )
        ApplicationApartmentFactory.create_application_with_apartments(
            [apartment.uuid], application
        )
        assert Customer.objects.count() == 1
    else:
        assert Customer.objects.count() == 0

    data = create_application_data(profile, num_applicants=1)

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == profile.id

    assert Profile.objects.count() == 1
    assert Customer.objects.count() == 1
    assert application.customer.secondary_profile is None


@pytest.mark.parametrize("already_existing_customer", (False, True, "wrong"))
@pytest.mark.django_db
def test_application_post_multi_profile_customer(
    api_client,
    elastic_single_project_with_apartments,
    already_existing_customer,
):
    profile = ProfileFactory()
    secondary_profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    application_end_time = timezone.now() + timedelta(days=10)
    if already_existing_customer:
        apartment = ApartmentDocumentFactory(
            project_application_end_time=application_end_time
        )
        if already_existing_customer is True:
            application = ApplicationFactory(
                customer=CustomerFactory(
                    primary_profile=profile,
                    secondary_profile=secondary_profile,
                    has_children=True,
                ),
            )
        else:
            application = ApplicationFactory(
                customer=CustomerFactory(
                    primary_profile=profile,
                    secondary_profile=ProfileFactory(),
                    has_children=True,
                ),
            )
        ApplicationApartmentFactory.create_application_with_apartments(
            [apartment.uuid], application
        )
        assert Customer.objects.count() == 1
    else:
        assert Customer.objects.count() == 0
    assert Profile.objects.count() == 3 if already_existing_customer == "wrong" else 2

    data = create_application_data(profile)
    if already_existing_customer is True:
        data["additional_applicant"][
            "date_of_birth"
        ] = f"{secondary_profile.date_of_birth:%Y-%m-%d}"
        data["additional_applicant"]["ssn_suffix"] = secondary_profile.ssn_suffix

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == profile.id
    if already_existing_customer is True:
        assert str(application.customer.secondary_profile_id) == secondary_profile.id
    else:
        assert application.customer.secondary_profile


@pytest.mark.django_db
def test_application_post_writes_audit_log(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    api_client.post(reverse("application_form:application-list"), data, format="json")
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "USER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "CREATE"
    assert audit_event["target"] == {
        "id": data["application_uuid"],
        "type": "Application",
    }
    assert audit_event["status"] == "SUCCESS"


@pytest.mark.django_db
def test_application_post_fails_if_not_authenticated(
    api_client, elastic_single_project_with_apartments
):
    data = create_application_data(ProfileFactory())
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_application_post_writes_audit_log_if_not_authenticated(
    api_client, elastic_single_project_with_apartments
):
    data = create_application_data(ProfileFactory())
    api_client.post(reverse("application_form:application-list"), data, format="json")
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert audit_event["operation"] == "CREATE"
    assert audit_event["target"] == {"id": None, "type": "Application"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
def test_application_post_fails_if_incorrect_ssn_suffix(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    data["applicant"]["ssn_suffix"] = "-000$"
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(response.data["applicant"]["ssn_suffix"][0]["message"]) > 0
    assert (
        response.data["applicant"]["ssn_suffix"][0]["code"]
        == error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID
    )


@pytest.mark.django_db
def test_application_post_fails_if_incorrect_ssn_suffix_additional_applicant(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    data["additional_applicant"]["ssn_suffix"] = "-000$"
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(response.data["additional_applicant"]["ssn_suffix"][0]["message"]) > 0
    assert (
        response.data["additional_applicant"]["ssn_suffix"][0]["code"]
        == error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID
    )


@pytest.mark.django_db
def test_application_post_fails_if_applicant_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if single applicant tries to send multiple applications. Only
    one application is allowed per project.
    """
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    application_data = create_application_data(profile, num_applicants=1)
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.django_db
def test_application_post_fails_if_applicants_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if applicants tries to send multiple applications. Only one
    application is allowed per project.
    """
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    application_data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.django_db
def test_application_post_fails_if_partner_applicant_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if same partner has set into two different applications. Only one
    application is allowed per project.
    """
    profile = ProfileFactory()
    application_data = create_application_data(profile)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    second_profile = ProfileFactory()
    second_application_data = create_application_data(second_profile)
    second_application_data["additional_applicant"]["ssn_suffix"] = application_data[
        "additional_applicant"
    ]["ssn_suffix"]
    second_application_data["additional_applicant"]["date_of_birth"] = application_data[
        "additional_applicant"
    ]["date_of_birth"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(second_profile)}")
    response = api_client.post(
        reverse("application_form:application-list"),
        second_application_data,
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.django_db
def test_application_post_fails_if_partner_profile_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if partner tries to use own profile in another application. Only one
    application is allowed per project.
    """
    profile = ProfileFactory()
    application_data = create_application_data(profile)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    partner_profile = ProfileFactory(
        date_of_birth=datetime.strptime(
            application_data["additional_applicant"]["date_of_birth"], "%Y-%m-%d"
        ).date(),
    )
    partner_application_data = create_application_data(partner_profile)
    partner_application_data["applicant"]["ssn_suffix"] = application_data[
        "additional_applicant"
    ]["ssn_suffix"]
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(partner_profile)}"
    )
    response = api_client.post(
        reverse("application_form:application-list"),
        partner_application_data,
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.parametrize(
    "application_type", (ApplicationType.HITAS, ApplicationType.HASO)
)
@pytest.mark.django_db
def test_application_post_generate_metadata(
    api_client,
    elastic_single_project_with_apartments,
    application_type,
):
    profile = ProfileFactory()
    secondary_profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    apartment = ApartmentDocumentFactory()
    application = ApplicationFactory(
        customer=CustomerFactory(
            primary_profile=profile, secondary_profile=secondary_profile
        ),
        type=application_type,
    )
    ApplicationApartmentFactory.create_application_with_apartments(
        [apartment.uuid], application
    )

    data = create_application_data(profile, application_type=application_type)
    data["additional_applicant"][
        "date_of_birth"
    ] = f"{secondary_profile.date_of_birth:%Y-%m-%d}"
    data["additional_applicant"]["ssn_suffix"] = secondary_profile.ssn_suffix
    data["additional_applicant"]["first_name"] = secondary_profile.first_name
    data["additional_applicant"]["last_name"] = secondary_profile.last_name

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert application.handler_information == METADATA_HANDLER_INFORMATION
    assert application.type == application_type
    assert (
        application.process_number == METADATA_HASO_PROCESS_NUMBER
        if application_type == ApplicationType.HASO
        else METADATA_HITAS_PROCESS_NUMBER
    )
    assert application.sender_names == "{}/ {}".format(
        profile.full_name, secondary_profile.full_name
    )
    assert application.method_of_arrival == ApplicationArrivalMethod.ELECTRONICAL_SYSTEM


@pytest.mark.parametrize(
    "application_type",
    (ApplicationType.HITAS, ApplicationType.PUOLIHITAS, ApplicationType.HASO),
)
@pytest.mark.django_db
def test_application_post_right_of_residence_auto_populating(
    api_client,
    elastic_single_project_with_apartments,
    application_type,
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(profile, application_type=application_type)
    if application_type == ApplicationType.HASO:
        data.pop("right_of_residence_is_old_batch", None)
    else:
        # this should be set to None because this is not a haso application
        data["right_of_residence_is_old_batch"] = True

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])

    if application_type == ApplicationType.HASO:
        # there was no value provided so this should contain the default value False
        assert application.right_of_residence_is_old_batch is False
    else:
        assert application.right_of_residence_is_old_batch is None


@pytest.mark.django_db
def test_haso_application_post_right_of_residence_can_be_set(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(profile, application_type=ApplicationType.HASO)
    data["right_of_residence_is_old_batch"] = True

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])

    assert application.right_of_residence_is_old_batch is True


@pytest.mark.parametrize("has_children", (False, True))
@pytest.mark.django_db
def test_application_post_single_profile_customer_has_children(
    api_client, elastic_single_project_with_apartments, has_children
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    assert Profile.objects.count() == 1
    assert Customer.objects.count() == 0

    data = create_application_data(profile, num_applicants=1)
    data["has_children"] = has_children

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == profile.id

    assert Profile.objects.count() == 1
    assert Customer.objects.count() == 1
    assert Customer.objects.first().has_children == has_children
    assert application.customer.secondary_profile is None


@pytest.mark.django_db
def test_get_apartment_states_unauthorized(
    api_client,
    user_api_client,
    profile_api_client,
    drupal_salesperson_api_client,
):
    response = api_client.get(reverse("application_form:apartment_states"))
    assert response.status_code == 403

    response = user_api_client.get(reverse("application_form:apartment_states"))
    assert response.status_code == 403

    response = profile_api_client.get(reverse("application_form:apartment_states"))
    assert response.status_code == 403

    response = drupal_salesperson_api_client.get(
        reverse("application_form:apartment_states")
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_get_apartment_states(
    drupal_server_api_client,
    elastic_haso_project_with_5_apartments,
    elastic_hitas_project_with_5_apartments,
):
    response = drupal_server_api_client.get(
        reverse("application_form:apartment_states")
    )
    assert response.status_code == 200
    assert response.data == {}
    haso_project_uuid, haso_apartments = elastic_haso_project_with_5_apartments
    hitas_project_uuid, hitas_apartments = elastic_hitas_project_with_5_apartments

    for apartment in haso_apartments[:4]:
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            state=ApartmentReservationState.RESERVED,
            list_position=1,
        )
        LotteryEventFactory.create(apartment_uuid=apartment.uuid)

    for apartment in hitas_apartments[:4]:
        LotteryEventFactory.create(apartment_uuid=apartment.uuid)

    # These apartments haven't been distributed yet, so change events of these
    # reservations should not be returned
    ApartmentReservationFactory(
        apartment_uuid=haso_apartments[4].uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
    )
    ApartmentReservationFactory(
        apartment_uuid=hitas_apartments[4].uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
    )

    # Sold apartments
    sold_reservations = ApartmentReservation.objects.filter(
        apartment_uuid=haso_apartments[1].uuid
    )
    assert sold_reservations.count() == 1
    sold_reservations[0].set_state(ApartmentReservationState.SOLD)

    # Sold apartment but ends with a cancellation event
    sold_reservations = ApartmentReservation.objects.filter(
        apartment_uuid=haso_apartments[2].uuid
    )
    sold_reservations[0].set_state(ApartmentReservationState.SOLD)
    cancelled_reservation = ApartmentReservationFactory(
        apartment_uuid=haso_apartments[2].uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=2,
    )
    cancelled_reservation.set_state(ApartmentReservationState.CANCELED
                                    )
    assert (
        ApartmentReservation.objects.filter(
            apartment_uuid=haso_apartments[2].uuid
        ).count()
        == 2
    )

    # Reserved hitas apartment
    ApartmentReservationFactory(
        apartment_uuid=hitas_apartments[0].uuid,
        state=ApartmentReservationState.RESERVED,
    )

    # Free apartment
    reserved_reservations = ApartmentReservation.objects.filter(
        apartment_uuid=haso_apartments[3].uuid
    )
    assert reserved_reservations.count() == 1
    reserved_reservations[0].set_state(ApartmentReservationState.CANCELED
                                       )

    response = drupal_server_api_client.get(
        reverse("application_form:apartment_states"),
        {"start_time": "2020-02-02", "end_time": "2020-01-02"},
    )
    assert response.status_code == 400
    assert "greater than end date" in response.data[0]["message"]

    response = drupal_server_api_client.get(
        reverse("application_form:apartment_states")
    )
    assert response.status_code == 200
    assert len(response.data.keys()) == 5
    assert response.data[haso_apartments[0].uuid] == ApartmentStateOfSale.RESERVED_HASO
    assert response.data[haso_apartments[1].uuid] == ApartmentStateOfSale.SOLD
    assert response.data[haso_apartments[2].uuid] == ApartmentStateOfSale.SOLD
    assert (
        response.data[haso_apartments[3].uuid]
        == ApartmentStateOfSale.FREE_FOR_RESERVATIONS
    )
    assert response.data[hitas_apartments[0].uuid] == ApartmentStateOfSale.RESERVED


@pytest.mark.django_db
def test_get_apartment_states_filter(
    drupal_server_api_client, elastic_single_project_with_apartments
):
    response = drupal_server_api_client.get(
        reverse("application_form:apartment_states")
    )
    assert response.status_code == 200
    assert response.data == {}
    apartments = elastic_single_project_with_apartments  # 10 apartments
    with freeze_time("2020-02-01"):
        for apartment in apartments:
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid, state=ApartmentReservationState.RESERVED
            )
            LotteryEventFactory(apartment_uuid=apartment.uuid)

    assert len(apartments) == 10
    sold_apartment_uuids_1 = [apt.uuid for apt in apartments[:5]]
    sold_apartment_uuids_2 = [apt.uuid for apt in apartments[5:]]
    sold_reservations_1 = ApartmentReservation.objects.filter(
        apartment_uuid__in=sold_apartment_uuids_1
    )
    sold_reservations_2 = ApartmentReservation.objects.filter(
        apartment_uuid__in=sold_apartment_uuids_2
    )

    # Sold some apartment in different date time
    with freeze_time("2020-02-02"):
        for sold_reservation in sold_reservations_1:
            sold_reservation.set_state(ApartmentReservationState.SOLD
                                       )
            sold_reservation.save()
    with freeze_time("2020-02-04"):
        for sold_reservation in sold_reservations_2:
            sold_reservation.set_state(ApartmentReservationState.SOLD)
            sold_reservation.save()
        response = drupal_server_api_client.get(
            reverse("application_form:apartment_states")
        )
        assert response.status_code == 200
        assert len(response.data.keys()) == 5
        assert sorted(response.data.keys()) == sorted(sold_apartment_uuids_2)

    response = drupal_server_api_client.get(
        reverse("application_form:apartment_states")
    )
    assert response.status_code == 200
    assert response.data == {}

@pytest.mark.django_db
def test_late_submit_application_post_existing_application_gets_canceled(
    api_client,
    elasticsearch,
):
    """
    Late submitting an application should cancel the existing application instead of deleting.
    """
    application_end_time = (datetime.now()+timedelta(days=2)).replace(
        tzinfo=timezone.get_default_timezone()
    )
    apartments = generate_apartments(
        elasticsearch,
        2,
        {
            "project_can_apply_afterwards": True, 
            "project_ownership_type": OwnershipType.HASO.value
        }
    )
    first_application_apartment = apartments[0]
    second_application_apartment = apartments[1]
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    first_application_data = create_application_data(
        profile, apartments=[first_application_apartment]
    )

    response = api_client.post(
        reverse("application_form:application-list"),
        first_application_data,
        format="json"
    )
    first_application: Application = Application.objects.get(
        external_uuid=response.json()["application_uuid"]
    )

    second_application_data = create_application_data(
        profile,
        apartments=[second_application_apartment]
    )
    response = api_client.post(
        reverse("application_form:application-list"), second_application_data, format="json"
    )
    first_reservation = ApartmentReservation.objects.get(
        apartment_uuid=apartments[0].uuid,
        application_apartment=first_application.application_apartments.first()
    )
    second_application: Application = Application.objects.get(
        external_uuid=response.json()["application_uuid"]
    )

    assert first_reservation.state == ApartmentReservationState.CANCELED

    pass

@pytest.mark.django_db
def test_application_post_haso_submitted_late_end_of_queue(
    # add_application_to_queues_mock, api_client, elasticsearch
    drupal_server_api_client,
    elasticsearch,
):
    """
    HASO Applications added late should be at the end of the queue regardless of
    the applicant's right of residence number
    """
    profile = ProfileFactory()

    drupal_server_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}"
    )

    late_customer_profile = ProfileFactory()

    drupal_server_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}"
    )

    application_start_time = (datetime.now() - timedelta(days=10)).replace(
        tzinfo=timezone.get_default_timezone()
    )
    application_end_time = application_start_time + timedelta(days=20)

    apartment_properties = {
        "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
        "_language": "fi",
        "project_application_start_time": application_start_time,
        "project_application_end_time": application_end_time,
        "project_ownership_type": OwnershipType.HASO.value,
        "project_can_apply_afterwards": True,
    }

    apartments = generate_apartments(elasticsearch, 2, apartment_properties)

    on_time_applications = []
    for idx in range(5):
        on_time_customer_profile = ProfileFactory()

        on_time_application_data = create_application_data(
            on_time_customer_profile, ApplicationType.HASO, 1, apartments
        )
        on_time_application_data["profile"] = on_time_customer_profile.id
        on_time_application_data["right_of_residence"] = 1000 + idx

        response = drupal_server_api_client.post(
            reverse("application_form:application-list"),
            on_time_application_data,
            format="json",
        )
        assert response.status_code == 201
        on_time_application = Application.objects.get(
            external_uuid=response.json()["application_uuid"]
        )
        on_time_applications.append(on_time_application)

    # create late applications
    late_applications = []
    for idx in range(5):
        late_customer_profile = ProfileFactory()
        late_application_data = create_application_data(
            late_customer_profile, ApplicationType.HASO, 1, apartments
        )
        late_application_data["profile"] = late_customer_profile.id
        late_application_data["right_of_residence"] = 1 + idx

        with freeze_time(application_end_time + timedelta(days=2)):
            drupal_server_api_client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {_create_token(late_customer_profile)}"
            )

            response = drupal_server_api_client.post(
                reverse("application_form:application-list"),
                late_application_data,
                format="json",
            )

            assert response.status_code == 201
            late_application = Application.objects.get(
                external_uuid=response.json()["application_uuid"]
            )

        late_applications.append(late_application)

    on_time_customer_profile = ProfileFactory()

    drupal_server_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(on_time_customer_profile)}"
    )
    on_time_application_data = create_application_data(
        on_time_customer_profile, ApplicationType.HASO, 1, apartments
    )

    on_time_reservations = ApartmentReservation.objects.filter(
        application_apartment__application__in=on_time_applications
    )
    late_reservations = ApartmentReservation.objects.filter(
        application_apartment__application__in=late_applications,
        # submitted_late=True
    )

    highest_on_time_queue_pos = max(
        on_time_reservations.values_list("queue_position", flat=True)
    )
    lowest_late_time_queue_pos = max(
        late_reservations.values_list("queue_position", flat=True)
    )

    # Reservations for late applications should be marked with submitted_late = True
    assert [*late_reservations.values_list("submitted_late", flat=True).distinct()] == [
        True
    ]

    # Applications submitted on time should be higher in queue than late submitted ones
    assert highest_on_time_queue_pos < lowest_late_time_queue_pos

    pass


@pytest.mark.django_db
@patch("application_form.services.application.EmailMessage")
def test_application_post_haso_submitted_late(
    EmailMessageMock: MagicMock, drupal_server_api_client, elasticsearch
):
    profile = ProfileFactory(
        first_name="Heikki",
        last_name="Hakija",
        email="heikki.hakija@mail.com",
    )
    drupal_server_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}"
    )
    application_start_time = (datetime.now() - timedelta(days=20)).replace(
        tzinfo=timezone.get_default_timezone()
    )
    application_end_time = application_start_time - timedelta(days=10)

    late_submit_haso_apartment_properties = {
        "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
        "_language": "fi",
        "project_application_start_time": application_start_time,
        "project_application_end_time": application_end_time,
        "project_ownership_type": OwnershipType.HASO.value,
        "project_can_apply_afterwards": True,
        "project_housing_company": "Testikatu 321",
        "project_estate_agent_email": "markku.myyja@mail.com",
    }

    apartments_late_submit: List[ApartmentDocument] = generate_apartments(
        elasticsearch, 5, late_submit_haso_apartment_properties
    )
    late_submit_data = create_application_data(
        profile, num_applicants=1, apartments=apartments_late_submit
    )

    late_submit_data["profile"] = profile.id

    response = drupal_server_api_client.post(
        reverse("application_form:application-list"), late_submit_data, format="json"
    )
    assert response.status_code == 201
    application = Application.objects.get(
        external_uuid=response.json()["application_uuid"]
    )
    assert application.submitted_late is True

    late_submit_reservation_count = ApartmentReservation.objects.filter(
        apartment_uuid__in=[ap.uuid for ap in apartments_late_submit],
        submitted_late=True,
    ).count()
    assert late_submit_reservation_count == len(apartments_late_submit)

    # ugly indentation to avoid text being unnecessarily indented in the email
    expected_body = f"""Kohteelle Testikatu 321 on tehty jälkihakemus.

Hakijan tiedot:
{profile.full_name}
{profile.email}

Haetut asunnot:\n"""

    for idx, apt in enumerate(apartments_late_submit):
        expected_body += f"{idx+1}. {apt.apartment_address}\n"

    # make sure email notification is sent to salesperson
    EmailMessageMock.assert_called_with(
        to=["markku.myyja@mail.com"],
        subject="Jälkihakemus Testikatu 321",
        body=expected_body,
    )

    assert EmailMessageMock().send.call_count == 1

    # make sure reservations are created
    assert ApartmentReservation.objects.filter(
        apartment_uuid__in=[apt.uuid for apt in apartments_late_submit],
    ).count() == len(apartments_late_submit)

    #  setting submitted_late to False manually in POST shouldnt be allowed
    customer_profile_2 = ProfileFactory()

    apartments_late_submit_manual = generate_apartments(
        elasticsearch, 5, late_submit_haso_apartment_properties
    )

    late_submit_manual_data = create_application_data(
        customer_profile_2, num_applicants=2, apartments=apartments_late_submit_manual
    )

    late_submit_manual_data["profile"] = customer_profile_2.id
    late_submit_manual_data["submitted_late"] = False

    response = drupal_server_api_client.post(
        reverse("application_form:application-list"),
        late_submit_manual_data,
        format="json",
    )
    assert response.status_code == 201
    second_application = Application.objects.get(
        external_uuid=response.json()["application_uuid"]
    )
    assert second_application.submitted_late is True

    # Test that HITAS apartment late submit isn't allowed (should only work with HASO)
    apartments_late_submit_hitas = generate_apartments(
        elasticsearch,
        5,
        {
            "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
            "_language": "fi",
            "project_application_start_time": application_start_time,
            "project_application_end_time": application_end_time,
            "project_ownership_type": OwnershipType.HITAS.value,
        },
    )

    customer_profile_3 = ProfileFactory()

    data = create_application_data(
        customer_profile_3, num_applicants=2, apartments=apartments_late_submit_hitas
    )
    data["profile"] = customer_profile_3.id
    response = drupal_server_api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code != 201

    # Test that ApartmentDocument.project_can_apply_afterwards is respected
    apartment_cant_apply_afterwards = generate_apartments(
        elasticsearch,
        10,
        {
            "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
            "_language": "fi",
            "project_application_start_time": application_start_time,
            "project_application_end_time": application_end_time,
            "project_can_apply_afterwards": False,
        },
    )
    customer_profile_4 = ProfileFactory()
    data = create_application_data(
        customer_profile_4,
        num_applicants=2,
        apartments=apartment_cant_apply_afterwards,
    )
    data["profile"] = customer_profile_4.id

    response = drupal_server_api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code != 201


@pytest.mark.parametrize(
    "application_type", (ApplicationType.HITAS, ApplicationType.HASO)
)
@pytest.mark.django_db
def test_drupal_user_can_only_delete_own_application(
    elastic_single_project_with_apartments, api_client, application_type
):
    application_owner_profile = ProfileFactory()
    apartment = ApartmentDocumentFactory()

    application_deleter_profile = ProfileFactory()
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(application_deleter_profile)}"
    )
    application = ApplicationFactory(
        customer=CustomerFactory(primary_profile=application_owner_profile),
        type=application_type,
    )
    ApplicationApartmentFactory.create_application_with_apartments(
        [apartment.uuid], application
    )

    response = api_client.delete(
        reverse(
            "application_form:application-delete",
            kwargs={"application_uuid": application.external_uuid},
        ),
    )

    assert response.status_code == 403
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(application_owner_profile)}"
    )
    response = api_client.delete(
        reverse(
            "application_form:application-delete",
            kwargs={"application_uuid": application.external_uuid},
        ),
    )
    assert response.status_code == 204


@pytest.mark.django_db
@pytest.mark.parametrize(
    "reservation_state",
    (
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.SOLD,
    ),
)
def test_application_to_already_reserved_project(
    api_client, elastic_single_project_with_apartments, reservation_state
):
    """
    Users who have a reservation with the state 'offered', 'offer_accepted' or 'sold'
    in a project shouldn't be allowed to create further applications to it.
    """
    apartment: ApartmentDocument = elastic_single_project_with_apartments[0]

    profile: Profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile)
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        state=reservation_state,
        application_apartment=ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid,
            application=ApplicationFactory(customer=customer, applicants_count=1),
        ),
    )

    data = create_application_data(profile, apartments=[apartment])
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code == 400
