import uuid
from logging import getLogger
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F

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
from application_form.utils import lock_table

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
                list_position = (
                    ApartmentReservation.objects.filter(
                        apartment_uuid=apartment_uuid
                    ).count()
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
        apartment_reservation.queue_position_before_cancelation = apartment_reservation.queue_position

    old_queue_position = apartment_reservation.queue_position
    apartment_reservation.queue_position = None
    apartment_reservation.save(update_fields=["queue_position", "queue_position_before_cancelation"])
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
        "application_apartment__application__right_of_residence",
        "application_apartment__application__right_of_residence_is_old_batch",
    )
    all_reservations = all_reservations.active()
    reservations = all_reservations.filter(
        application_apartment__application__submitted_late=submitted_late
    ).order_by("queue_position")
    for apartment_reservation in reservations:
        other_application = apartment_reservation.application_apartment.application
        if (
            right_of_residence_ordering_number
            < other_application.right_of_residence_ordering_number
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
