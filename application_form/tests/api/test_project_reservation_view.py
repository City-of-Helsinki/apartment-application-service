import pytest
from django.urls import reverse

from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
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
    for apartment in apartments:
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid, application=application
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
    for apartment in apartments:
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid, application=application
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
        assert item["queue_position"] is None


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
