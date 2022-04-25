import uuid
from django.utils import timezone

from apartment.elastic.queries import get_apartment_uuids, get_projects
from application_form.exceptions import ProjectDoesNotHaveApplicationsException
from application_form.models import ApartmentReservation, Application, LotteryEvent
from application_form.services.lottery.exceptions import (
    ApplicationTimeNotFinishedException,
)


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
            result_position=apartment_reservation.list_position,
        )


def _validate_project_has_applications(project_uuid: uuid.UUID):
    apartment_uuids = get_apartment_uuids(project_uuid)
    application_count = Application.objects.filter(
        application_apartments__apartment_uuid__in=apartment_uuids
    ).count()
    if application_count == 0:
        raise ProjectDoesNotHaveApplicationsException()


def _validate_project_application_time_has_finished(project_uuid: uuid.UUID):
    project = get_projects(project_uuid)[0]
    if (
        not project.project_application_end_time
        or project.project_application_end_time >= timezone.now()
    ):
        raise ApplicationTimeNotFinishedException()
