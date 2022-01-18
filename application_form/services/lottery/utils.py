import uuid

from application_form.models import ApartmentReservation, LotteryEvent


def _save_application_order(apartment_uuid: uuid.UUID) -> None:
    """
    Persist the apartment queue for the given apartment in the database.
    This creates a new lottery event for the apartment and associates the apartment
    applications to that event in the order of their current queue position.

    If the apartment queue has already been recorded, then this function does nothing;
    a lottery is performed only once and therefore its result is stored only once.
    """
    if LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).exists():
        return  # don't record it twice
    event = LotteryEvent.objects.create(apartment_uuid=apartment_uuid)
    reservations = ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)
    for apartment_reservation in reservations:
        event.results.create(
            application_apartment=apartment_reservation.application_apartment,
            result_position=apartment_reservation.queue_position,
        )
