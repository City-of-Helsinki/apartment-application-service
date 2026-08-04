import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.translation import gettext

from apartment.utils import get_apartment_state_of_sale_from_event
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation
from application_form.tests.conftest import create_application_data
from application_form.tests.factories import ApartmentReservationFactory
from connections.enums import ApartmentStateOfSale
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.fixture
def sold_apartment_with_winner(elastic_single_project_with_apartments):
    """
    First apartment in the fixture project with an existing sold reservation.

    Returns:
        tuple: (sold apartment document, sold reservation).
    """
    sold_apartment = elastic_single_project_with_apartments[0]
    sold_reservation = ApartmentReservationFactory(
        apartment_uuid=sold_apartment.uuid,
        state=ApartmentReservationState.SOLD,
        list_position=1,
        queue_position=1,
    )
    return sold_apartment, sold_reservation


@pytest.mark.django_db
@override_settings(ALLOW_APPLICATIONS_TO_SOLD_APARTMENTS=False)
def test_application_to_sold_apartment_is_rejected(
    api_client,
    sold_apartment_with_winner,
):
    """
    Customer applications to sold apartments must be rejected.

    - POST /v1/applications/ returns 400 when blocking is enabled.
    - No new reservation is created for another customer.
    """
    sold_apartment, sold_reservation = sold_apartment_with_winner
    reservation_count_before = ApartmentReservation.objects.count()

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile, apartments=[sold_apartment])

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code == 400
    assert str(response.data["detail"]["message"]) == gettext(
        "Cannot apply to a sold apartment"
    )
    assert ApartmentReservation.objects.count() == reservation_count_before
    sold_reservation.refresh_from_db()
    assert sold_reservation.state == ApartmentReservationState.SOLD


@pytest.mark.django_db
@override_settings(ALLOW_APPLICATIONS_TO_SOLD_APARTMENTS=False)
def test_sales_application_to_sold_apartment_is_rejected(
    drupal_salesperson_api_client,
    sold_apartment_with_winner,
):
    """
    Sales applications to sold apartments must be rejected.

    - POST /v1/sales/applications/ returns 400 when blocking is enabled.
    """
    sold_apartment, _sold_reservation = sold_apartment_with_winner
    customer_profile = ProfileFactory()
    drupal_salesperson_api_client.credentials(
        HTTP_AUTHORIZATION=(
            f"Bearer {_create_token(drupal_salesperson_api_client.user.profile)}"
        )
    )
    data = create_application_data(customer_profile, apartments=[sold_apartment])
    data["profile"] = customer_profile.id

    response = drupal_salesperson_api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )

    assert response.status_code == 400
    assert str(response.data["detail"]["message"]) == gettext(
        "Cannot apply to a sold apartment"
    )


@pytest.mark.django_db
@override_settings(ALLOW_APPLICATIONS_TO_SOLD_APARTMENTS=False)
def test_application_to_unsold_apartment_succeeds_when_blocking_enabled(
    api_client,
    elastic_single_project_with_apartments,
    sold_apartment_with_winner,
):
    """
    Applications to non-sold apartments must still succeed when blocking is on.

    - Positive control for the sold-apartment guard.
    """
    sold_apartment, _ = sold_apartment_with_winner
    free_apartment = next(
        apartment
        for apartment in elastic_single_project_with_apartments
        if apartment.uuid != sold_apartment.uuid
    )

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile, apartments=[free_apartment])

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code == 201


@pytest.mark.django_db
@override_settings(ALLOW_APPLICATIONS_TO_SOLD_APARTMENTS=True)
def test_application_to_sold_apartment_allowed_when_bypass_enabled(
    api_client,
    sold_apartment_with_winner,
):
    """
    Test environments may allow applications to sold apartments.

    - Application is created when bypass is enabled.
    - The sold winner reservation and apartment state of sale stay SOLD.
    """
    sold_apartment, sold_reservation = sold_apartment_with_winner
    sold_event = sold_reservation.state_change_events.last()

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile, apartments=[sold_apartment])

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code == 201

    sold_reservation.refresh_from_db()
    assert sold_reservation.state == ApartmentReservationState.SOLD
    assert sold_reservation.queue_position == 1
    assert (
        get_apartment_state_of_sale_from_event(sold_event) == ApartmentStateOfSale.SOLD
    )

    new_reservations = ApartmentReservation.objects.filter(
        apartment_uuid=sold_apartment.uuid
    ).exclude(pk=sold_reservation.pk)
    assert new_reservations.exists()
    assert all(
        reservation.state == ApartmentReservationState.SUBMITTED
        for reservation in new_reservations
    )
