import pytest
from django.urls import reverse

from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import (
    add_application_to_queues,
    remove_reservation_from_queue,
)
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    LotteryEventFactory,
    LotteryEventResultFactory,
)
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
def test_list_project_reservations_get(api_client, elastic_project_with_5_apartments):
    """
    Test that the API endpoint returns the project's reservations
    by the profile id and project UUID.
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    apartment_reservation_count = 5
    profile = ProfileFactory()
    application = ApplicationFactory(customer=CustomerFactory(primary_profile=profile))
    for i, apartment in enumerate(apartments):
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid,
            application=application,
            priority_number=i + 1,
        )
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid, application_apartment=application_apartment
        )
        event = LotteryEventFactory(apartment_uuid=apartment.uuid)
        LotteryEventResultFactory(
            event=event, application_apartment=application_apartment
        )

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": project_uuid}
    response = api_client.get(
        reverse("application_form:list_project_reservations", kwargs=data),
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == apartment_reservation_count


@pytest.mark.django_db
def test_list_project_reservations_get_without_lottery_data(
    api_client, elastic_project_with_5_apartments
):
    """
    Test that the project's reservations will be returned correctly
    if the lottery is not yet performed.
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    apartment_reservation_count = 5
    profile = ProfileFactory()
    application = ApplicationFactory(customer=CustomerFactory(primary_profile=profile))
    for i, apartment in enumerate(apartments):
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid,
            application=application,
            priority_number=i + 1,
        )
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid, application_apartment=application_apartment
        )

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": project_uuid}
    response = api_client.get(
        reverse("application_form:list_project_reservations", kwargs=data),
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == apartment_reservation_count
    for item in response.data:
        assert item["lottery_position"] is None
        assert item["queue_position"] is not None


@pytest.mark.django_db
def test_list_project_reservations_get_with_lottery_data(
    api_client, elastic_haso_project_with_5_apartments
):
    """
    Test that the project's reservations will be returned correctly
    if the lottery is already performed.
    """
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    apartment_reservation_count = 5
    profile = ProfileFactory()
    application = ApplicationFactory(customer=CustomerFactory(primary_profile=profile))
    for idx, apartment in enumerate(apartments):
        ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid, application=application, priority_number=idx
        )
    add_application_to_queues(application)
    distribute_apartments(project_uuid)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = {"project_uuid": project_uuid}
    response = api_client.get(
        reverse("application_form:list_project_reservations", kwargs=data),
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == apartment_reservation_count
    for item in response.data:
        assert item["lottery_position"] == 1
        # Auto cancel reservations which have lower priority
        # so queue position should be None
        assert item["queue_position"] == (1 if item["priority_number"] == 0 else None)


@pytest.mark.django_db
def test_list_project_reservations_new_fields_non_cancelled(
    api_client, elastic_project_with_5_apartments
):
    """
    For a non-cancelled reservation all cancellation fields must be null
    and state_change_events must contain at least the initial submitted entry.
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    application = ApplicationFactory(customer=CustomerFactory(primary_profile=profile))
    apartment = apartments[0]
    application_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=application,
        priority_number=1,
    )
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, application_apartment=application_apartment
    )

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse(
            "application_form:list_project_reservations",
            kwargs={"project_uuid": project_uuid},
        ),
        format="json",
    )

    assert response.status_code == 200
    item = response.data[0]

    # New fields present for non-cancelled reservation
    assert "state_change_events" in item
    assert len(item["state_change_events"]) >= 1
    assert item["state_change_events"][0]["state"] == ApartmentReservationState.SUBMITTED.value  # noqa: E501
    assert item["cancellation_reason"] is None
    assert "cancellation_reason_display" not in item
    assert item["cancellation_actor"] is None
    assert "cancellation_actor_label" not in item
    assert item["cancellation_timestamp"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cancellation_reason, expected_actor",
    [
        # Seller-initiated: manual actions and offer rejection recorded by seller
        (
            ApartmentReservationCancellationReason.TERMINATED,
            "seller",
        ),
        (
            ApartmentReservationCancellationReason.CANCELED,
            "seller",
        ),
        (
            ApartmentReservationCancellationReason.RESERVATION_AGREEMENT_CANCELED,
            "seller",
        ),
        (
            ApartmentReservationCancellationReason.TRANSFERRED,
            "seller",
        ),
        # offer_rejected: seller records it in the system on behalf of the customer
        (
            ApartmentReservationCancellationReason.OFFER_REJECTED,
            "seller",
        ),
        # System-initiated: automatic pipeline actions, no human actor
        (
            ApartmentReservationCancellationReason.LOWER_PRIORITY,
            "system",
        ),
        (
            ApartmentReservationCancellationReason.OTHER_APARTMENT_OFFERED,
            "system",
        ),
    ],
)
def test_list_project_reservations_cancellation_actor(
    api_client,
    elastic_project_with_5_apartments,
    cancellation_reason,
    expected_actor,
):
    """
    Verify cancellation_actor for every cancellation reason.
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    application = ApplicationFactory(customer=CustomerFactory(primary_profile=profile))
    apartment = apartments[0]
    application_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=application,
        priority_number=1,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, application_apartment=application_apartment
    )
    remove_reservation_from_queue(
        reservation, cancellation_reason=cancellation_reason
    )

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse(
            "application_form:list_project_reservations",
            kwargs={"project_uuid": project_uuid},
        ),
        format="json",
    )

    assert response.status_code == 200
    item = response.data[0]

    assert item["state"] == ApartmentReservationState.CANCELED.value
    assert item["cancellation_reason"] == cancellation_reason.value
    assert "cancellation_reason_display" not in item
    assert item["cancellation_actor"] == expected_actor
    assert "cancellation_actor_label" not in item
    assert item["cancellation_timestamp"] is not None