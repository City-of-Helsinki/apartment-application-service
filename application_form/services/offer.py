from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apartment_application_service.utils import update_obj
from application_form.enums import ApartmentReservationState, OfferState
from application_form.models import Offer

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

    return offer
