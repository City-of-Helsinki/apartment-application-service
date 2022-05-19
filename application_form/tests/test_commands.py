import pytest
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone

from application_form.enums import ApartmentReservationState, OfferState
from application_form.tests.factories import OfferFactory


@pytest.mark.django_db
def test_update_reservations_based_on_offer_expiration():
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    offers = (
        # these reservation states should stay the same
        OfferFactory(
            valid_until=yesterday,
            state=OfferState.PENDING,
            apartment_reservation__state=ApartmentReservationState.RESERVED,
        ),
        OfferFactory(
            valid_until=today,
            state=OfferState.PENDING,
            apartment_reservation__state=ApartmentReservationState.OFFERED,
        ),
        OfferFactory(
            valid_until=yesterday,
            state=OfferState.PENDING,
            apartment_reservation__state=ApartmentReservationState.OFFER_EXPIRED,
        ),
        OfferFactory(
            valid_until=yesterday,
            state=OfferState.ACCEPTED,
            apartment_reservation__state=ApartmentReservationState.OFFER_ACCEPTED,
        ),
        OfferFactory(
            valid_until=yesterday,
            state=OfferState.REJECTED,
            apartment_reservation__state=ApartmentReservationState.CANCELED,
        ),
        # these reservation states should change
        OfferFactory(
            valid_until=yesterday,
            state=OfferState.PENDING,
            apartment_reservation__state=ApartmentReservationState.OFFERED,
        ),
        OfferFactory(
            valid_until=today,
            state=OfferState.PENDING,
            apartment_reservation__state=ApartmentReservationState.OFFER_EXPIRED,
        ),
    )

    call_command(
        "update_reservations_based_on_offer_expiration",
    )

    expected_states = (
        ApartmentReservationState.RESERVED,
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_EXPIRED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.CANCELED,
        ApartmentReservationState.OFFER_EXPIRED,
        ApartmentReservationState.OFFERED,
    )

    for offer, expected_state in zip(offers, expected_states):
        offer.apartment_reservation.refresh_from_db()
        assert offer.apartment_reservation.state == expected_state
