from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apartment_application_service.utils import update_obj
from application_form.enums import ApartmentReservationState, OfferState
from application_form.models import ApartmentReservation, Offer

User = get_user_model()


@transaction.atomic()
def create_offer(offer_data: dict, user: User = None) -> Offer:
    if hasattr(offer_data["apartment_reservation"], "offer"):
        raise ValidationError(
            f"Cannot create an offer to reservation "
            f"{offer_data['apartment_reservation'].id} "
            f"because it already has an offer."
        )

    offer = Offer.objects.create(**offer_data)
    offer_data["apartment_reservation"].set_state(
        ApartmentReservationState.OFFERED, user=user
    )

    return offer


@transaction.atomic()
def update_offer(offer: Offer, offer_data: dict, user: User = None) -> Offer:
    if offer.state != OfferState.PENDING:
        for field in ("state", "valid_until"):
            if field in offer_data and offer_data[field] != getattr(offer, field):
                raise ValidationError(
                    'Only comment can be edited when state is "accepted" or "rejected".'
                )

    new_offer_state = offer_data.get("state")
    if new_offer_state and new_offer_state != OfferState.PENDING:
        if new_offer_state == OfferState.ACCEPTED:
            new_reservation_state = ApartmentReservationState.OFFER_ACCEPTED
        elif new_offer_state == OfferState.REJECTED:
            new_reservation_state = ApartmentReservationState.CANCELED
        else:
            raise ValueError(f"Invalid OfferState: {new_offer_state}")
        offer.apartment_reservation.set_state(new_reservation_state, user=user)
        offer.concluded_at = timezone.now()

    update_obj(offer, offer_data)
    update_reservation_state_based_on_offer_expiration(offer.apartment_reservation)

    return offer


def update_reservation_state_based_on_offer_expiration(
    reservation: ApartmentReservation,
    user: User = None,
):
    update_reservations_based_on_offer_expiration(
        ApartmentReservation.objects.filter(pk=reservation.pk),
        user=user,
    )


def update_reservations_based_on_offer_expiration(
    reservation_qs=None, user: User = None
) -> (int, int):
    today = timezone.localdate()

    if not reservation_qs:
        reservation_qs = ApartmentReservation.objects.all()
    reservation_qs = reservation_qs.filter(offer__state=OfferState.PENDING)

    new_expired_reservations = reservation_qs.filter(
        state=ApartmentReservationState.OFFERED,
        offer__valid_until__lt=today,
    )
    not_anymore_expired_reservations = reservation_qs.filter(
        state=ApartmentReservationState.OFFER_EXPIRED,
        offer__valid_until__gte=today,
    )

    for reservation in new_expired_reservations:
        reservation.set_state(ApartmentReservationState.OFFER_EXPIRED, user=user)
    for reservation in not_anymore_expired_reservations:
        reservation.set_state(ApartmentReservationState.OFFERED, user=user)

    return new_expired_reservations.count(), not_anymore_expired_reservations.count()
