import logging
from typing import Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Max, QuerySet
from rest_framework.exceptions import ValidationError

from apartment.elastic.queries import get_apartment
from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import ApartmentReservation
from application_form.services.queue import _make_room_for_reservation
from application_form.utils import lock_table
from customer.models import Customer

_logger = logging.getLogger(__name__)

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
        handler=user.profile_or_user_full_name,
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


def calculate_haso_positions(
    reservations, right_of_residence_ordering_number
) -> Optional[Tuple[int, int]]:
    """
    Calculate new queue position in late reservations based on
    right of residence ordering number if right of residence is not smaller
    than any of the existing reservations just return keep the max queue position + 1
    """
    for apartment_reservation in reservations:
        if (
            right_of_residence_ordering_number
            < apartment_reservation.right_of_residence_ordering_number
            and apartment_reservation.queue_position is not None
        ):
            return (
                apartment_reservation.queue_position,
                apartment_reservation.list_position,
            )
    return None


def create_late_reservation(
    reservation_data: dict, user: User = None
) -> ApartmentReservation:
    with lock_table(ApartmentReservation):
        apartment_uuid = reservation_data["apartment_uuid"]
        apartment = get_apartment(apartment_uuid, include_project_fields=True)
        existing_reservations = get_existing_reservations(apartment_uuid)

        state = get_reservation_state(existing_reservations)
        max_list_position, max_queue_position = get_max_positions(existing_reservations)

        if user:
            reservation_data["handler"] = user.profile_or_user_full_name

        ownership_type = apartment.project_ownership_type.lower()
        right_of_residence_ordering_number = get_right_of_residence_ordering_number(
            reservation_data
        )
        if right_of_residence_ordering_number is None and ownership_type == "haso":
            raise ValidationError("User has no right of residence number set")

        new_list_position, new_queue_position = calculate_new_positions(
            max_list_position,
            max_queue_position,
            ownership_type,
            right_of_residence_ordering_number,
            existing_reservations,
        )
        reservation = create_reservation(
            reservation_data, state, new_list_position, new_queue_position, user
        )
        reservation.save(user=user)

        return reservation


def get_existing_reservations(apartment_uuid: str) -> QuerySet:
    return ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)


def get_reservation_state(existing_reservations: QuerySet) -> str:
    if existing_reservations.reserved().exists():
        return ApartmentReservationState.SUBMITTED
    return ApartmentReservationState.RESERVED


def get_max_positions(existing_reservations: QuerySet) -> tuple:
    max_list_position = existing_reservations.aggregate(
        max_list_position=Max("list_position")
    )["max_list_position"]
    max_queue_position = existing_reservations.exclude(
        state=ApartmentReservationState.CANCELED
    ).aggregate(max_queue_position=Max("queue_position"))["max_queue_position"]
    return max_list_position, max_queue_position


def get_right_of_residence_ordering_number(reservation_data: dict) -> int:
    return reservation_data["customer"].right_of_residence_ordering_number


def calculate_new_positions(
    max_list_position: int,
    max_queue_position: int,
    ownership_type: str,
    right_of_residence_ordering_number: int,
    existing_reservations: QuerySet,
) -> tuple:
    new_list_position = (max_list_position or 0) + 1
    new_queue_position = (max_queue_position or 0) + 1

    if ownership_type.lower() == "haso":
        late_reservations = (
            existing_reservations.filter(submitted_late=True)
            .exclude(state=ApartmentReservationState.OFFERED)
            .order_by("list_position")
        )
        if late_reservations:
            positions = calculate_haso_positions(
                late_reservations,
                right_of_residence_ordering_number,
            )
            if positions is not None:
                new_queue_position, new_list_position = positions
            _make_room_for_reservation(
                late_reservations, new_list_position, new_queue_position
            )

    return new_list_position, new_queue_position


def create_reservation(
    reservation_data: dict,
    state: str,
    list_position: int,
    queue_position: int,
    user: User,
) -> ApartmentReservation:
    customer = reservation_data["customer"]
    return ApartmentReservation(
        **reservation_data,
        state=state,
        list_position=list_position,
        submitted_late=True,
        queue_position=queue_position,
        right_of_residence=customer.right_of_residence,
        right_of_residence_is_old_batch=customer.right_of_residence_is_old_batch,
        has_children=customer.has_children,
        has_hitas_ownership=customer.has_hitas_ownership,
        is_age_over_55=customer.is_age_over_55,
        is_right_of_occupancy_housing_changer=customer.is_right_of_occupancy_housing_changer,  # noqa: E501
    )
