import uuid

from django.contrib.auth import get_user_model
from django.utils import timezone

from apartment.elastic.queries import get_apartment_uuids, get_project
from apartment_application_service.settings import METADATA_HANDLER_INFORMATION
from application_form.exceptions import ProjectDoesNotHaveApplicationsException
from application_form.models import ApartmentReservation, Application, LotteryEvent
from application_form.services.lottery.exceptions import (
    ApplicationTimeNotFinishedException,
)
from audit_log import audit_logging
from audit_log.enums import Operation

User = get_user_model()


def _save_application_order(apartment_uuid: uuid.UUID, user: User = None) -> None:
    """
    Persist the apartment queue for the given apartment in the database.
    This creates a new lottery event for the apartment and associates the apartment
    applications to that event in the order of their current queue position.

    If the apartment queue has already been recorded, then this function does nothing;
    a lottery is performed only once and therefore its result is stored only once.

    The salesperson's name who initiate the lottery will be stored in the DB
    """
    if LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).exists():
        return  # don't record it twice

    event = LotteryEvent.objects.create(
        apartment_uuid=apartment_uuid,
    )
    if user:
        event.handler = (
            METADATA_HANDLER_INFORMATION + " / " + user.profile_or_user_full_name
        )
        event.save()
    reservations = ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)
    for apartment_reservation in reservations:
        event.results.create(
            application_apartment=apartment_reservation.application_apartment,
            result_position=apartment_reservation.list_position,
        )
        if user:
            apartment_reservation.handler = user.profile_or_user_full_name
            apartment_reservation.save()
    audit_logging.log(user, Operation.CREATE, event)


def _validate_project_has_applications(project_uuid: uuid.UUID):
    apartment_uuids = get_apartment_uuids(project_uuid)
    application_count = Application.objects.filter(
        application_apartments__apartment_uuid__in=apartment_uuids
    ).count()
    if application_count == 0:
        raise ProjectDoesNotHaveApplicationsException()


def _validate_project_application_time_has_finished(project_uuid: uuid.UUID):
    project = get_project(project_uuid)
    application_end_time = project.project_application_end_time
    if not application_end_time:
        raise ApplicationTimeNotFinishedException()
    if timezone.is_naive(application_end_time):
        application_end_time = timezone.make_aware(application_end_time)
    if application_end_time >= timezone.now():
        raise ApplicationTimeNotFinishedException()
