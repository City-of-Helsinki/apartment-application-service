import uuid

from apartment.elastic.queries import get_apartment_uuids
from application_form.exceptions import ProjectDoesNotHaveApplicationsException
from application_form.models import ApartmentReservation, Application, LotteryEvent


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


def _validate_project_has_applications(project_uuid: uuid.UUID):
    apartment_uuids = get_apartment_uuids(project_uuid)
    application_count = Application.objects.filter(
        application_apartments__apartment_uuid__in=apartment_uuids
    ).count()
    if application_count == 0:
        raise ProjectDoesNotHaveApplicationsException()
