from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F

from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import ApartmentReservation
from customer.models import Customer

User = get_user_model()


@transaction.atomic
def transfer_reservation_to_another_customer(
    old_reservation: ApartmentReservation,
    customer: Customer,
    user: User = None,
    comment: str = None,
):
    """Transfer a reservation from one customer to another.

    Technically the reservation isn't transferred, it is set cancelled and a new one is
    created instead. The new reservation will get a list position right after the
    cancelled old one."""

    # Get the new reservation's field values ready but don't save it yet to keep it from
    # messing up reservation shifting
    new_reservation = ApartmentReservation(
        apartment_uuid=old_reservation.apartment_uuid,
        queue_position=old_reservation.queue_position,
        list_position=old_reservation.list_position + 1,
        state=old_reservation.state,
        customer=customer,
    )

    # Shift reservations after the old reservation one step back to make room for the
    # new reservation. We don't need to update queue positions because they will stay
    # the same when transferring a reservation.
    reservations_after_old_reservation = ApartmentReservation.objects.filter(
        apartment_uuid=old_reservation.apartment_uuid,
        list_position__gt=old_reservation.list_position,
    )
    reservations_after_old_reservation.update(list_position=F("list_position") + 1)

    new_reservation.save()
    new_reservation.queue_change_events.create(
        type=ApartmentQueueChangeEventType.ADDED,
    )

    old_reservation.queue_position = None
    old_reservation.save(update_fields=("queue_position",))
    state_change_event = old_reservation.set_state(
        ApartmentReservationState.CANCELED,
        user=user,
        comment=comment,
        cancellation_reason=ApartmentReservationCancellationReason.TRANSFERRED,
        replaced_by=new_reservation,
    )

    return state_change_event
