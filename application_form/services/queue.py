import uuid
from logging import getLogger
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Max

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartment
from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Application,
    ApplicationApartment,
)
from application_form.services.constants import LIST_POSITION_BUMP_OFFSET
from application_form.utils import lock_table
from customer.models import Customer

logger = getLogger(__name__)

User = get_user_model()


def add_application_to_queues(
    application: Application, comment: str = "", user: Optional[User] = None
) -> None:
    """
    Adds the given application to the queues of all the apartments applied to.
    """

    for application_apartment in application.application_apartments.all():

        apartment_uuid = application_apartment.apartment_uuid
        with lock_table(ApartmentReservation):
            if application.type == ApplicationType.HASO:
                # For HASO applications, the queue position is determined by the
                # right of residence number.
                # The list position will be the same as queue position
                queue_position = _calculate_queue_position(
                    apartment_uuid, application_apartment
                )
                list_position = queue_position
                # Need to shift both list position and queue position
                res = ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)

                _make_room_for_reservation(res, list_position, queue_position)
            elif application.type in [
                ApplicationType.HITAS,
                ApplicationType.PUOLIHITAS,
            ]:
                # HITAS and PUOLIHITAS work the same way from the apartment lottery
                # perspective, and should always be added to the end of the queue.
                try:
                    queue_position = (
                        ApartmentReservation.objects.active()
                        .filter(apartment_uuid=apartment_uuid)
                        .order_by("-queue_position")[0]
                        .queue_position
                        + 1
                    )
                except IndexError:
                    queue_position = 1

                apartment_reservations = ApartmentReservation.objects.filter(
                    apartment_uuid=apartment_uuid
                )
                if not apartment_reservations.exists():
                    list_position = 1
                else:
                    # Use Max("list_position") instead of reservation count
                    # to fix a corner case where the queue has an empty gap in
                    # list_positions
                    list_position = (
                        apartment_reservations.aggregate(
                            max_list_position=Max("list_position")
                        )["max_list_position"]
                        + 1
                    )
            else:
                raise ValueError(f"unsupported application type {application.type}")

            application = application_apartment.application
            apartment_reservation = ApartmentReservation(
                customer=application.customer,
                queue_position=queue_position,
                list_position=list_position,
                application_apartment=application_apartment,
                apartment_uuid=apartment_uuid,
                right_of_residence=application.right_of_residence,
                right_of_residence_is_old_batch=application.right_of_residence_is_old_batch,  # noqa: E501
                has_children=application.has_children,
                has_hitas_ownership=application.has_hitas_ownership,
                is_age_over_55=application.customer.is_age_over_55,
                is_right_of_occupancy_housing_changer=application.is_right_of_occupancy_housing_changer,  # noqa: E501
                submitted_late=application.submitted_late,
            )
            apartment_reservation.save(user=user)

            apartment_reservation.queue_change_events.create(
                type=ApartmentQueueChangeEventType.ADDED,
                comment=comment,
            )


@transaction.atomic
def remove_reservation_from_queue(
    apartment_reservation: ApartmentReservation,
    user: User = None,
    comment: str = None,
    cancellation_reason: ApartmentReservationCancellationReason = None,
) -> ApartmentReservationStateChangeEvent:
    """
    Removes the application from the queue of the given apartment. This essentially
    means that the application for this specific apartment was canceled, so the state
    of the application for this apartment will also be updated to "CANCELED".
    """
    if apartment_reservation.queue_position is not None:
        apartment_reservation.queue_position_before_cancelation = (
            apartment_reservation.queue_position
        )

    old_queue_position = apartment_reservation.queue_position
    apartment_reservation.queue_position = None
    apartment_reservation.save(
        update_fields=["queue_position", "queue_position_before_cancelation"]
    )
    _remove_queue_position(apartment_reservation.apartment_uuid, old_queue_position)
    state_change_event = apartment_reservation.set_state(
        ApartmentReservationState.CANCELED,
        user=user,
        comment=comment,
        cancellation_reason=cancellation_reason,
    )
    apartment_reservation.queue_change_events.create(
        type=ApartmentQueueChangeEventType.REMOVED, comment=comment or ""
    )

    return state_change_event


def remove_queue_gaps(apartment: ApartmentDocument):
    """Goes through `ApartmentReservation` rows and removes any gaps in the
    `queue_position` and `list_position` numbers.

    Orders the reservations by queue_position, loops through them
    and assigns iterator+1 as the `ApartmentReservation.queue_position`-attribute
    removing the gaps and preserving the current order.

    e.g. queue_positions `<empty> -> 2. -> <empty> -> 4. -> 5.`
    become `1. -> 2. -> 3.`

    DOES NOT help if the order of the queue needs to be recalculated entirely, e.g.
    in a situation where a late submitted reservation is changed to a regular one and
    its position should be changed to reflect that.

    Args:
        apartment (ApartmentDocument): The apartment whose queue is being modified
    """
    reservations = ApartmentReservation.objects.filter(
        apartment_uuid=apartment.uuid
    ).order_by("queue_position")

    # workaround:
    # list_position has an unique_together constraint with apartment_uuid
    # it also cannot be NULL
    # so we just temporarily move the list_positions out of the way
    # so we can set them into order with their queue_positions
    reservations.update(list_position=F("list_position") + LIST_POSITION_BUMP_OFFSET)

    for idx, res in enumerate(reservations, 1):
        res.set_state(state=res.state, queue_position=idx)
        res.list_position = idx
        res.save()


def _calculate_queue_position(
    apartment_uuid: uuid.UUID,
    application_apartment: ApplicationApartment,
) -> int:
    """
    Finds the new position in the queue for the given application based on its right
    of residence number. The smaller the number, the smaller the position in the queue.

    Late applications form a pool of their own and should be kept in the order of their
    right of residence number within that pool.
    """
    right_of_residence_ordering_number = (
        application_apartment.application.right_of_residence_ordering_number
    )
    submitted_late = application_apartment.application.submitted_late
    all_reservations = ApartmentReservation.objects.filter(
        apartment_uuid=apartment_uuid
    ).only(
        "queue_position",
        "state",
        "application_apartment__application__right_of_residence",
        "application_apartment__application__right_of_residence_is_old_batch",
    )
    all_reservations = all_reservations.active()
    reservations = all_reservations.filter(
        application_apartment__application__submitted_late=submitted_late
    ).order_by("queue_position")

    offered_or_sold_states = [
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.SOLD,
    ]
    for apartment_reservation in reservations:
        other_application = apartment_reservation.application_apartment.application

        if (
            right_of_residence_ordering_number
            < other_application.right_of_residence_ordering_number
            and apartment_reservation.state not in offered_or_sold_states
        ):
            return apartment_reservation.queue_position
    return all_reservations.count() + 1


def _make_room_for_reservation(res, new_list_position, new_queue_position):
    """
    Make room for a new reservation by shifting list and queue
    positions.

    This function is used when adding a new reservation to the queue. It
    shifts all reservations that are >= the new list position and >= the
    new queue position by one.
    """
    _adjust_positions(res, "list_position", new_list_position, by=1)
    _adjust_positions(res, "queue_position", new_queue_position, by=1)


def _remove_queue_position(apartment_uuid, queue_position):
    """
    Remove a queue position from the reservations list.

    This function is used when cancelling a reservation in the queue. It
    shifts all reservations that are >= the queue position by -1, i.e.
    decreasing their queue position by 1.
    """
    if queue_position is None:
        logger.warning(
            "from_position is None, bad reservation data in apartment uuid"
            f"{apartment_uuid}?"
        )
        return
    res = ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)
    _adjust_positions(res, "queue_position", queue_position, by=-1)


def _adjust_positions(reservations, position_field, from_position, *, by):
    """
    Adjust list or queue positions of reservations by given amount.

    position_field should be either "list_position" or "queue_position".
    """
    res_from_pos = reservations.filter(**{position_field + "__gte": from_position})
    res_from_pos.update(**{position_field: F(position_field) + by})


def preview_queue_change(
    apartment_uuid: uuid.UUID,
    *,
    reservation_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    queue_position: Optional[int] = None,
    submitted_late: Optional[bool] = None,
    state: Optional[str] = None,
) -> list:
    """Calculate reservation queue preview in memory without DB writes."""
    reservations = list(
        ApartmentReservation.objects.related_fields()
        .filter(apartment_uuid=apartment_uuid)
        .order_by("list_position")
    )

    if reservation_id is not None:
        _apply_edit_in_memory(
            reservations=reservations,
            apartment_uuid=apartment_uuid,
            reservation_id=reservation_id,
            queue_position=queue_position,
            submitted_late=submitted_late,
            state=state,
        )
    elif customer_id is not None:
        customer = Customer.objects.select_related(
            "primary_profile", "secondary_profile"
        ).get(id=customer_id)
        apartment = get_apartment(apartment_uuid, include_project_fields=True)
        _apply_add_in_memory(
            reservations=reservations,
            apartment_uuid=apartment_uuid,
            customer=customer,
            ownership_type=(apartment.project_ownership_type or "").lower(),
            queue_position=queue_position,
            submitted_late=submitted_late,
        )

    return reservations


def _state_value(state) -> str:
    return state.value if hasattr(state, "value") else str(state)


def _is_active(reservation: ApartmentReservation) -> bool:
    return _state_value(reservation.state) != ApartmentReservationState.CANCELED.value


def _adjust_positions_in_memory(
    reservations: list, position_field: str, from_position: int, by: int
) -> None:
    for reservation in reservations:
        position = getattr(reservation, position_field)
        if position is not None and position >= from_position:
            setattr(reservation, position_field, position + by)


def _apply_edit_in_memory(
    *,
    reservations: list,
    apartment_uuid: uuid.UUID,
    reservation_id: int,
    queue_position: Optional[int],
    submitted_late: Optional[bool],
    state: Optional[str],
) -> None:
    target = next((r for r in reservations if r.id == reservation_id), None)
    if target is None:
        return

    others = [r for r in reservations if r.id != reservation_id]

    if submitted_late is not None:
        submitted_late_changed = target.submitted_late != submitted_late
        target.submitted_late = submitted_late
    else:
        submitted_late_changed = False

    if state == ApartmentReservationState.CANCELED.value:
        old_position = target.queue_position
        target.queue_position = None
        target.state = ApartmentReservationState.CANCELED
        if old_position is not None:
            _adjust_positions_in_memory(others, "queue_position", old_position, -1)
        return

    if state:
        target.state = state

    if queue_position is not None and queue_position != target.queue_position:
        old_position = target.queue_position
        if old_position is not None:
            _adjust_positions_in_memory(others, "queue_position", old_position, -1)

        active_others = [reservation for reservation in others if _is_active(reservation)]
        clamped_position = max(1, min(queue_position, len(active_others) + 1))
        _adjust_positions_in_memory(others, "queue_position", clamped_position, 1)
        target.queue_position = clamped_position
    elif submitted_late_changed and _is_active(target):
        apartment = get_apartment(apartment_uuid, include_project_fields=True)
        if (apartment.project_ownership_type or "").lower() == "haso":
            ordering_number = target.right_of_residence_ordering_number
            if ordering_number is None:
                return

            old_position = target.queue_position
            if old_position is not None:
                _adjust_positions_in_memory(others, "queue_position", old_position, -1)

            active_others = [reservation for reservation in others if _is_active(reservation)]
            same_late_group = sorted(
                [
                    reservation
                    for reservation in active_others
                    if reservation.submitted_late == target.submitted_late
                ],
                key=lambda reservation: reservation.queue_position or 0,
            )
            offered_or_sold_states = {
                ApartmentReservationState.OFFER_ACCEPTED.value,
                ApartmentReservationState.OFFERED.value,
                ApartmentReservationState.SOLD.value,
            }
            new_position = len(active_others) + 1
            for reservation in same_late_group:
                reservation_ordering_number = (
                    reservation.right_of_residence_ordering_number
                )
                if (
                    reservation_ordering_number is not None
                    and ordering_number < reservation_ordering_number
                    and _state_value(reservation.state) not in offered_or_sold_states
                ):
                    new_position = reservation.queue_position
                    break

            _adjust_positions_in_memory(others, "queue_position", new_position, 1)
            target.queue_position = new_position


def _determine_new_reservation_state(active_reservations: list) -> ApartmentReservationState:
    for reservation in active_reservations:
        if _state_value(reservation.state) == ApartmentReservationState.RESERVED.value:
            return ApartmentReservationState.SUBMITTED
    return ApartmentReservationState.RESERVED


def _apply_add_in_memory(
    *,
    reservations: list,
    apartment_uuid: uuid.UUID,
    customer: Customer,
    ownership_type: str,
    queue_position: Optional[int],
    submitted_late: Optional[bool],
) -> None:
    effective_submitted_late = submitted_late if submitted_late is not None else True
    active_reservations = [reservation for reservation in reservations if _is_active(reservation)]

    if queue_position is not None:
        new_queue_position = max(1, min(queue_position, len(active_reservations) + 1))
        _adjust_positions_in_memory(reservations, "queue_position", new_queue_position, 1)
    elif ownership_type == "haso":
        ordering_number = customer.right_of_residence_ordering_number
        if ordering_number is None:
            new_queue_position = len(active_reservations) + 1
        else:
            same_late_group = sorted(
                [
                    reservation
                    for reservation in active_reservations
                    if reservation.submitted_late == effective_submitted_late
                ],
                key=lambda reservation: reservation.queue_position or 0,
            )
            offered_or_sold_states = {
                ApartmentReservationState.OFFER_ACCEPTED.value,
                ApartmentReservationState.OFFERED.value,
                ApartmentReservationState.SOLD.value,
            }
            new_queue_position = len(active_reservations) + 1
            for reservation in same_late_group:
                reservation_ordering_number = (
                    reservation.right_of_residence_ordering_number
                )
                if (
                    reservation_ordering_number is not None
                    and ordering_number < reservation_ordering_number
                    and _state_value(reservation.state) not in offered_or_sold_states
                ):
                    new_queue_position = reservation.queue_position
                    break

            _adjust_positions_in_memory(
                reservations, "queue_position", new_queue_position, 1
            )
    else:
        new_queue_position = len(active_reservations) + 1

    max_list_position = max(
        (reservation.list_position for reservation in reservations), default=0
    )
    preview_reservation = ApartmentReservation(
        apartment_uuid=apartment_uuid,
        customer=customer,
        state=_determine_new_reservation_state(active_reservations),
        list_position=max_list_position + 1,
        queue_position=new_queue_position,
        submitted_late=effective_submitted_late,
        right_of_residence=customer.right_of_residence,
        right_of_residence_is_old_batch=customer.right_of_residence_is_old_batch,
        has_children=customer.has_children,
        has_hitas_ownership=customer.has_hitas_ownership,
        is_age_over_55=customer.is_age_over_55,
        is_right_of_occupancy_housing_changer=(
            customer.is_right_of_occupancy_housing_changer
        ),
    )
    reservations.append(preview_reservation)
