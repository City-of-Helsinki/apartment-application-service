import uuid
from django.db import transaction
from django.db.models import F

from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models import (
    ApartmentReservation,
    Application,
    ApplicationApartment,
)


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
                position = _calculate_queue_position(
                    apartment_uuid, application_apartment
                )
                _shift_queue_positions(apartment_uuid, position)
            elif application.type in [
                ApplicationType.HITAS,
                ApplicationType.PUOLIHITAS,
            ]:
                # HITAS and PUOLIHITAS work the same way from the apartment lottery
                # perspective, and should always be added to the end of the queue.
                position = (
                    ApartmentReservation.objects.filter(
                        apartment_uuid=apartment_uuid
                    ).count()
                    + 1
                )
            else:
                raise ValueError(f"unsupported application type {application.type}")

            apartment_reservation = ApartmentReservation.objects.create(
                customer=application_apartment.application.customer,
                queue_position=position,
                application_apartment=application_apartment,
                apartment_uuid=apartment_uuid,
            )
            apartment_reservation.queue_change_events.create(
                type=ApartmentQueueChangeEventType.ADDED,
                comment=comment,
            )


@transaction.atomic
def remove_application_from_queue(
    application_apartment: ApplicationApartment,
    comment: str = "",
) -> None:
    """
    Removes the application from the queue of the given apartment. This essentially
    means that the application for this specific apartment was canceled, so the state
    of the application for this apartment will also be updated to "CANCELED".
    """
    apartment_reservation = application_apartment.apartment_reservation
    _shift_queue_positions(
        apartment_reservation.apartment_uuid,
        apartment_reservation.queue_position,
        deleted=True,
    )
    application_apartment.apartment_reservation.set_state(
        ApartmentReservationState.CANCELED
    )
    apartment_reservation.queue_change_events.create(
        type=ApartmentQueueChangeEventType.REMOVED, comment=comment
    )


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


def _shift_queue_positions(
    apartment_uuid: uuid.UUID, from_position: int, deleted: bool = False
) -> None:
    """
    Shifts all items in the queue by one by either incrementing or decrementing their
    positions, depending on whether the item was added or deleted from the queue.
    """
    # We only need to update the positions in the queue that are >= from_position
    reservations = ApartmentReservation.objects.filter(
        apartment_uuid=apartment_uuid, queue_position__gte=from_position
    )
    # When deleting, we have to decrement each position. When adding, increment instead.
    position_change = -1 if deleted else 1
    reservations.update(queue_position=F("queue_position") + position_change)
