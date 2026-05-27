from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    OfferState,
)
from application_form.models import ApartmentReservationStateChangeEvent
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    OfferFactory,
)
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


def _create_offered_reservation(profile, apartment=None):
    """
    Build a reservation in OFFERED state with a pending offer for the profile.
    """
    if apartment is None:
        apartment = ApartmentDocumentFactory()
    customer = CustomerFactory(primary_profile=profile)
    application = ApplicationFactory(customer=customer)
    application_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=application,
        priority_number=1,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment=application_apartment,
        customer=customer,
        state=ApartmentReservationState.OFFERED,
    )
    offer = OfferFactory(
        apartment_reservation=reservation,
        state=OfferState.PENDING,
        valid_until=timezone.localdate() + timedelta(days=7),
    )
    return reservation, offer


def _customer_client(profile):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    return client


@pytest.mark.django_db
def test_customer_accept_offer(api_client):
    """
    - Accept happy path: offer ACCEPTED, reservation OFFER_ACCEPTED, event recorded.
    """
    profile = ProfileFactory()
    reservation, offer = _create_offered_reservation(profile)
    client = _customer_client(profile)

    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "accepted"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["state"] == "accepted"
    assert response.data["concluded_at"] is not None

    offer.refresh_from_db()
    reservation.refresh_from_db()
    assert offer.state == OfferState.ACCEPTED
    assert reservation.state == ApartmentReservationState.OFFER_ACCEPTED
    assert ApartmentReservationStateChangeEvent.objects.filter(
        reservation=reservation, state=ApartmentReservationState.OFFER_ACCEPTED
    ).exists()


@pytest.mark.django_db
def test_customer_reject_offer(api_client):
    """
    - Reject happy path: offer REJECTED, reservation CANCELED with OFFER_REJECTED.
    """
    profile = ProfileFactory()
    reservation, offer = _create_offered_reservation(profile)
    client = _customer_client(profile)

    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "rejected"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["state"] == "rejected"

    offer.refresh_from_db()
    reservation.refresh_from_db()
    assert offer.state == OfferState.REJECTED
    assert reservation.state == ApartmentReservationState.CANCELED
    cancel_event = ApartmentReservationStateChangeEvent.objects.filter(
        reservation=reservation, state=ApartmentReservationState.CANCELED
    ).latest("timestamp")
    assert (
        cancel_event.cancellation_reason
        == ApartmentReservationCancellationReason.OFFER_REJECTED
    )


@pytest.mark.django_db
def test_customer_offer_update_other_profile_returns_404(api_client):
    """
    - 404 when offer belongs to a different profile.
    """
    owner = ProfileFactory()
    other = ProfileFactory()
    _, offer = _create_offered_reservation(owner)
    client = _customer_client(other)

    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "accepted"},
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_customer_offer_update_secondary_profile_returns_404(api_client):
    """
    - 404 when secondary profile attempts (primary profile only).
    """
    primary = ProfileFactory()
    secondary = ProfileFactory()
    customer = CustomerFactory(primary_profile=primary, secondary_profile=secondary)
    apartment = ApartmentDocumentFactory()
    application = ApplicationFactory(customer=customer)
    application_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=application,
        priority_number=1,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment=application_apartment,
        customer=customer,
        state=ApartmentReservationState.OFFERED,
    )
    offer = OfferFactory(
        apartment_reservation=reservation,
        state=OfferState.PENDING,
        valid_until=timezone.localdate() + timedelta(days=7),
    )
    client = _customer_client(secondary)

    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "accepted"},
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.parametrize("offer_state", ("accepted", "rejected"))
@pytest.mark.django_db
def test_customer_offer_update_already_concluded_returns_400(api_client, offer_state):
    """
    - 400 for already accepted / already rejected offer.
    """
    profile = ProfileFactory()
    reservation, offer = _create_offered_reservation(profile)
    offer.state = OfferState(offer_state)
    offer.concluded_at = timezone.now()
    offer.save(update_fields=["state", "concluded_at"])
    client = _customer_client(profile)

    new_state = "rejected" if offer_state == "accepted" else "accepted"
    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": new_state},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_customer_offer_update_expired_returns_400(api_client):
    """
    - 400 for expired pending offer.
    """
    profile = ProfileFactory()
    reservation, offer = _create_offered_reservation(profile)
    offer.valid_until = timezone.localdate() - timedelta(days=1)
    offer.save(update_fields=["valid_until"])
    client = _customer_client(profile)

    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "accepted"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_customer_offer_update_invalid_state_returns_400(api_client):
    """
    - 400 for invalid state value.
    """
    profile = ProfileFactory()
    _, offer = _create_offered_reservation(profile)
    client = _customer_client(profile)

    response = client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "pending"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_customer_offer_update_unauthorized(api_client):
    """
    - 401 without JWT.
    """
    profile = ProfileFactory()
    _, offer = _create_offered_reservation(profile)

    response = api_client.patch(
        reverse(
            "application_form:customer_offer_update",
            kwargs={"offer_id": offer.pk},
        ),
        data={"state": "accepted"},
        format="json",
    )

    assert response.status_code == 401
