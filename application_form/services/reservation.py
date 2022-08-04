from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Max

from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import ApartmentReservation
from application_form.utils import lock_table
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
        handler=user.profile.full_name,
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


def create_reservation(
    reservation_data: dict, user: User = None
) -> ApartmentReservation:
    with lock_table(ApartmentReservation):
        existing_reservations = ApartmentReservation.objects.filter(
            apartment_uuid=reservation_data["apartment_uuid"]
        )

        if existing_reservations.reserved().exists():
            state = ApartmentReservationState.SUBMITTED
        else:
            state = ApartmentReservationState.RESERVED

        max_list_position = existing_reservations.aggregate(
            max_list_position=Max("list_position")
        )["max_list_position"]
        max_queue_position = existing_reservations.exclude(
            state=ApartmentReservationState.CANCELED
        ).aggregate(max_queue_position=Max("queue_position"))["max_queue_position"]

        if user:
            reservation_data["handler"] = user.full_name

        reservation = ApartmentReservation(
            **reservation_data,
            state=state,
            list_position=(max_list_position or 0) + 1,
            queue_position=(max_queue_position or 0) + 1,
            right_of_residence=reservation_data["customer"].right_of_residence,
            has_children=reservation_data["customer"].has_children,
            has_hitas_ownership=reservation_data["customer"].has_hitas_ownership,
            is_age_over_55=reservation_data["customer"].is_age_over_55,
            is_right_of_occupancy_housing_changer=reservation_data[
                "customer"
            ].is_right_of_occupancy_housing_changer,  # noqa: E501
        )
        reservation.save(user=user)

    return reservation
