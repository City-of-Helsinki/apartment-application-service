import pytest
from django.urls import reverse

from apartment.tests.factories import ApartmentFactory, ProjectFactory
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    LotteryEventFactory,
    LotteryEventResultFactory,
)
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
def test_list_project_reservations_get(api_client):
    """
    Test that the API endpoint returns the project's reservations
    by the profile id and project UUID.
    """
    apartment_reservation_count = 5
    profile = ProfileFactory()
    project = ProjectFactory()
    apartments = ApartmentFactory.create_batch(
        apartment_reservation_count, project=project
    )
    application = ApplicationFactory(profile=profile)
    for apartment in apartments:
        application_apartment = ApplicationApartmentFactory(
            apartment=apartment, application=application
        )
        ApartmentReservationFactory(
            apartment=apartment, application_apartment=application_apartment
        )
        event = LotteryEventFactory(apartment=apartment)
        LotteryEventResultFactory(
            event=event, application_apartment=application_apartment
        )

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": project.uuid}
    response = api_client.get(
        reverse("application_form:list_project_reservations", kwargs=data),
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == apartment_reservation_count


@pytest.mark.django_db
def test_list_project_reservations_get_without_lottery_data(api_client):
    """
    Test that the project's reservations will be returned correctly
    if the lottery is not yet performed.
    """
    apartment_reservation_count = 5
    profile = ProfileFactory()
    project = ProjectFactory()
    apartments = ApartmentFactory.create_batch(5, project=project)
    application = ApplicationFactory(profile=profile)
    for apartment in apartments:
        application_apartment = ApplicationApartmentFactory(
            apartment=apartment, application=application
        )
        ApartmentReservationFactory(
            apartment=apartment, application_apartment=application_apartment
        )

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": project.uuid}
    response = api_client.get(
        reverse("application_form:list_project_reservations", kwargs=data),
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == apartment_reservation_count
    for item in response.data:
        assert item["lottery_position"] is None
