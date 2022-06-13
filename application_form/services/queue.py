import uuid
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

User = get_user_model()


def add_application_to_queues(application: Application, comment: str = "") -> None:
    """
    Adds the given application to the queues of all the apartments applied to.
    """
    for application_apartment in application.application_apartments.all():
        apartment_uuid = application_apartment.apartment_uuid
        with transaction.atomic():
            if application.type == ApplicationType.HASO:
                # For HASO applications, the queue position is determined by the
                # right of residence number.
                # The list position will be the same as queue position
                queue_position = _calculate_queue_position(
                    apartment_uuid, application_apartment
                )
                list_position = queue_position
                # Need to shift both list position and queue position
                _shift_positions(apartment_uuid, queue_position)
            elif application.type in [
                ApplicationType.HITAS,
                ApplicationType.PUOLIHITAS,
            ]:
                # HITAS and PUOLIHITAS work the same way from the apartment lottery
                # perspective, and should always be added to the end of the queue.
                try:
                    queue_position = (
                        ApartmentReservation.objects.filter(
                            apartment_uuid=apartment_uuid
                        )
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
            apartment_reservation = ApartmentReservation.objects.create(
                customer=application.customer,
                queue_position=queue_position,
                list_position=list_position,
                application_apartment=application_apartment,
                apartment_uuid=apartment_uuid,
                right_of_residence=application.right_of_residence,
            )
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
    old_queue_position = apartment_reservation.queue_position
    apartment_reservation.queue_position = None
    apartment_reservation.save(update_fields=("queue_position",))
    _shift_positions(
        apartment_reservation.apartment_uuid,
        old_queue_position,
        deleted=True,
    )
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
    right_of_residence = application_apartment.application.right_of_residence
    submitted_late = application_apartment.application.submitted_late
    all_reservations = ApartmentReservation.objects.filter(
        apartment_uuid=apartment_uuid
    ).only("queue_position", "application_apartment__application__right_of_residence")
    reservations = all_reservations.filter(
        application_apartment__application__submitted_late=submitted_late
    ).order_by("queue_position")
    for apartment_reservation in reservations:
        other_application = apartment_reservation.application_apartment.application
        if right_of_residence < other_application.right_of_residence:
            return apartment_reservation.queue_position
    return all_reservations.count() + 1


def _shift_positions(
    apartment_uuid: uuid.UUID,
    from_position: int,
    deleted: bool = False,
) -> None:
    """
    Shifts all items in the queue by one by either incrementing or decrementing their
    positions, depending on whether the item was added or deleted from the queue.

    NOTE: This function cannot be used for adding after the apartment's lottery has been
    executed, because then there can be cancelled reservations, and for those the
    shifting won't work correctly.
    """
    reservations = ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)
    if not deleted and reservations.filter(queue_position=None).exists():
        raise RuntimeError(
            "This function cannot be used for adding a reservation when the apartment "
            "has reservations without a queue_position."
        )

    # We only need to update the positions in the queue that are >= from_position
    reservations = reservations.filter(queue_position__gte=from_position)

    # When deleting, we have to decrement each position. When adding, increment instead.
    position_change = -1 if deleted else 1
    reservations.update(queue_position=F("queue_position") + position_change)
    if not deleted:
        reservations.update(list_position=F("list_position") + position_change)
