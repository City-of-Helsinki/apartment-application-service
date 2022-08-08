from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apartment.elastic.queries import get_apartment, get_apartment_uuids
from apartment_application_service.utils import update_obj
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    OfferState,
)
from application_form.models import ApartmentReservation, Offer
from application_form.services.application import cancel_reservation

User = get_user_model()


@transaction.atomic()
def create_offer(offer_data: dict, user: User = None) -> Offer:
    apartment_reservation = offer_data["apartment_reservation"]
    if hasattr(apartment_reservation, "offer"):
        raise ValidationError(
            f"Cannot create an offer to reservation "
            f"{offer_data['apartment_reservation'].id} "
            f"because it already has an offer."
        )
    if user:
        offer_data["handler"] = user.full_name
    offer = Offer.objects.create(**offer_data)
    apartment_reservation.set_state(ApartmentReservationState.OFFERED, user=user)
    update_other_customer_reservations_states(apartment_reservation)

    return offer


@transaction.atomic()
def update_offer(offer: Offer, offer_data: dict, user: User = None) -> Offer:
    if offer.state != OfferState.PENDING:
        for field in ("state", "valid_until"):
            if field in offer_data and offer_data[field] != getattr(offer, field):
                raise ValidationError(
                    'Only comment can be edited when state is "accepted" or "rejected".'
                )

    if "state" in offer_data and offer_data["state"] != offer.state:
        if offer_data["state"] == OfferState.ACCEPTED:
            offer.apartment_reservation.set_state(
                ApartmentReservationState.OFFER_ACCEPTED, user=user
            )
        elif offer_data["state"] == OfferState.REJECTED:
            cancel_reservation(offer.apartment_reservation, user=user)
        else:
            raise ValueError(f'Invalid OfferState: {offer_data["state"]}')
        offer.concluded_at = timezone.now()
    if user:
        offer_data["handler"] = user.full_name
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


def update_other_customer_reservations_states(reservation):
    apartment = get_apartment(reservation.apartment_uuid, include_project_fields=True)
    other_reservations = ApartmentReservation.objects.filter(
        apartment_uuid__in=get_apartment_uuids(apartment.project_uuid),
        customer=reservation.customer,
    ).exclude(Q(state=ApartmentReservationState.CANCELED) | Q(id=reservation.id))
    for reservation in other_reservations:
        cancel_reservation(
            reservation,
            cancellation_reason=ApartmentReservationCancellationReason.OTHER_APARTMENT_OFFERED,  # noqa: E501
            comment="Tarjottu {}".format(apartment.apartment_number),
        )
