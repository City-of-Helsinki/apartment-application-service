import logging
import uuid
from datetime import date
from typing import Iterable, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet

from apartment.elastic.queries import get_apartment
from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
    ApplicationApartment,
)
from application_form.services.queue import (
    add_application_to_queues,
    remove_reservation_from_queue,
)
from audit_log import audit_logging
from audit_log.enums import Operation
from customer.services import get_or_create_customer_from_profiles

_logger = logging.getLogger(__name__)

User = get_user_model()


@transaction.atomic
def cancel_reservation(
    apartment_reservation: ApartmentReservation,
    user: User = None,
    comment: str = None,
    cancellation_reason: ApartmentReservationCancellationReason = None,
) -> ApartmentReservationStateChangeEvent:
    """
    Mark the reservation as canceled and remove it from the apartment queue.

    If the reservation has already won the apartment, then the winner for the apartment
    will be recalculated.
    """
    was_reserved = (
        apartment_reservation.state is not ApartmentReservationState.SUBMITTED
    )
    apartment_uuid = apartment_reservation.apartment_uuid
    apartment = get_apartment(apartment_uuid, include_project_fields=True)

    if (ownership_type := apartment.project_ownership_type.upper()) not in (
        "HASO",
        "HITAS",
        "PUOLIHITAS",
    ):
        raise ValueError(
            f"Apartment {apartment_reservation.apartment_uuid} has an invalid "
            f"project_ownership_type {ownership_type}"
        )

    state_change_event = remove_reservation_from_queue(
        apartment_reservation,
        user=user,
        comment=comment,
        cancellation_reason=cancellation_reason,
    )

    if was_reserved:
        if ownership_type == "HASO":
            _reserve_haso_apartment(apartment_uuid)
        else:
            _reserve_apartments([apartment_uuid], False)

    # Audit logging
    audit_logging.log(user, Operation.UPDATE, apartment_reservation)
    return state_change_event


@transaction.atomic
def create_application(
    application_data: dict, user: Optional[User] = None
) -> Application:
    _logger.debug(
        "Creating a new application with external UUID %s",
        application_data["external_uuid"],
    )
    data = application_data.copy()
    profile = data.pop("profile")
    additional_applicant_data = data.pop("additional_applicant")
    customer = get_or_create_customer_from_profiles(
        profile, additional_applicant_data, data.get("has_children")
    )
    application = Application.objects.create(
        external_uuid=data.pop("external_uuid"),
        applicants_count=2 if additional_applicant_data else 1,
        type=data.pop("type"),
        has_children=data.pop("has_children"),
        right_of_residence=data.pop("right_of_residence"),
        right_of_residence_is_old_batch=data.pop(
            "right_of_residence_is_old_batch", None
        ),
        has_hitas_ownership=data.pop("has_hitas_ownership"),
        is_right_of_occupancy_housing_changer=data.pop(
            "is_right_of_occupancy_housing_changer"
        ),
        customer=customer,
        process_number=data.pop("process_number"),
        handler_information=data.pop("handler_information"),
        method_of_arrival=data.pop("method_of_arrival"),
        sender_names=data.pop("sender_names"),
    )
    Applicant.objects.create(
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        phone_number=profile.phone_number,
        street_address=profile.street_address,
        city=profile.city,
        postal_code=profile.postal_code,
        age=_calculate_age(profile.date_of_birth),
        date_of_birth=profile.date_of_birth,
        ssn_suffix=application_data["ssn_suffix"],
        contact_language=profile.contact_language,
        is_primary_applicant=True,
        application=application,
    )
    if additional_applicant_data:
        Applicant.objects.create(
            first_name=additional_applicant_data["first_name"],
            last_name=additional_applicant_data["last_name"],
            email=additional_applicant_data["email"],
            phone_number=additional_applicant_data["phone_number"],
            street_address=additional_applicant_data["street_address"],
            city=additional_applicant_data["city"],
            postal_code=additional_applicant_data["postal_code"],
            age=_calculate_age(additional_applicant_data["date_of_birth"]),
            date_of_birth=additional_applicant_data["date_of_birth"],
            ssn_suffix=additional_applicant_data["ssn_suffix"],
            application=application,
        )
    apartment_data = data.pop("apartments")
    for apartment_item in apartment_data:
        ApplicationApartment.objects.create(
            application=application,
            apartment_uuid=apartment_item["identifier"],
            priority_number=apartment_item["priority"],
        )

    _logger.debug(
        "Application created with external UUID %s", application_data["external_uuid"]
    )
    add_application_to_queues(application, user=user)
    return application


def get_ordered_applications(apartment_uuid: uuid.UUID) -> QuerySet:
    """
    Returns a list of all applications for the given apartment, ordered by their
    position in the queue.
    """
    return Application.objects.filter(
        application_apartments__in=ApplicationApartment.objects.filter(
            apartment_uuid=apartment_uuid
        ).exclude(
            apartment_reservation__queue_change_events__type=ApartmentQueueChangeEventType.REMOVED  # noqa: E501
        )
    ).order_by("application_apartments__apartment_reservation__queue_position")


def _cancel_lower_priority_apartments(
    application_apartment: ApplicationApartment,
    cancel_reserved: bool = True,
) -> List[ApplicationApartment]:
    """
    Given the winning apartment application, cancel each apartment application for the
    same project that has a lower priority than the reserved apartment, no matter what
    position they are in the queue. The canceled application is removed from the queue
    of the corresponding apartment.

    An applicant can only have one apartment reserved at a time. If the applicant has,
    for example, priority 2 apartment reserved, then the lower priority apartments will
    be given to other applicants. However, the applicant will still be queuing for the
    first-priority apartment.
    """
    states_to_cancel = [ApartmentReservationState.SUBMITTED]
    if cancel_reserved:
        states_to_cancel.append(ApartmentReservationState.RESERVED)
    app_apartments = application_apartment.application.application_apartments.all()
    lower_priority_app_apartments = app_apartments.filter(
        priority_number__gt=application_apartment.priority_number,
        apartment_reservation__state__in=states_to_cancel,
    )
    canceled_winners = []
    for app_apartment in lower_priority_app_apartments:
        if app_apartment.apartment_reservation.queue_position == 1:
            canceled_winners.append(app_apartment)
        cancel_reservation(
            app_apartment.apartment_reservation,
            cancellation_reason=ApartmentReservationCancellationReason.LOWER_PRIORITY,
        )
    return canceled_winners


def _calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _reserve_apartments(
    apartment_uuids: Iterable[uuid.UUID],
    cancel_lower_priority_reserved: bool = True,
) -> None:
    apartments_to_process = set(list(apartment_uuids))
    while apartments_to_process:
        for apartment_uuid in apartments_to_process.copy():
            apartments_to_process.remove(apartment_uuid)
            # Mark the winner as "RESERVED"
            winner = _reserve_apartment(apartment_uuid)
            if winner is None:
                continue
            # If the winner has lower priority applications, we should cancel them.
            # This will modify the queues of other apartments, and if the apartment's
            # winner gets canceled, that apartment must be processed again.
            canceled_winners = _cancel_lower_priority_apartments(
                winner, cancel_lower_priority_reserved
            )
            apartments_to_process.update(app.apartment_uuid for app in canceled_winners)


def _reserve_haso_apartment(apartment_uuid: uuid.UUID) -> None:
    """
    Declare a winner for the given apartment.

    The application with the smallest right of residence number will be the winner.
    If there is a single winner, the state of that application will be changed to
    "RESERVED". If there are multiple winner candidates with the same right of residence
    number, their state will be changed to "REVIEW".

    If a winner has applied to other apartments in the same project with lower priority,
    then the applications with lower priority will be canceled and removed from their
    respective queues, unless their state is already "RESERVED".
    """
    # Get the applications in the queue, ordered by their queue position
    applications = get_ordered_applications(apartment_uuid)

    # There can be a single winner, or multiple winners if there are several
    # winning candidates with the same right of residence number.
    winning_applications = _find_winning_candidates(applications)

    if winning_applications.exists():
        # Set the reservation state to either "RESERVED" or "REVIEW"
        _update_reservation_state(winning_applications, apartment_uuid)

        # At this point the winner has been decided, but the winner may have outstanding
        # applications to other apartments. If they are lower priority, they should be
        # marked as "CANCELED" and deleted from the respective queues.
        _cancel_lower_priority_haso_applications(winning_applications, apartment_uuid)
    else:
        # There are no applications so the winning reservation is the one that is first
        # in the queue.
        winning_reservation = ApartmentReservation.objects.first_in_queue(
            apartment_uuid
        )
        if winning_reservation:
            winning_reservation.set_state(ApartmentReservationState.RESERVED)


def _update_reservation_state(
    applications: QuerySet, apartment_uuid: uuid.UUID
) -> None:
    """
    Update the state of the apartment application to either "RESERVED" or "REVIEW",
    depending on whether there is one or more winning candidates.
    """
    application_state = ApartmentReservationState.RESERVED
    if applications.count() > 1:
        application_state = ApartmentReservationState.REVIEW
    for application in applications:
        application_apartment = application.application_apartments.get(
            apartment_uuid=apartment_uuid
        )
        application_apartment.apartment_reservation.set_state(application_state)


def _reserve_apartment(apartment_uuid: uuid.UUID) -> Optional[ApplicationApartment]:
    # The winning application is whoever is at first position in the queue
    winning_application = get_ordered_applications(apartment_uuid).first()

    if winning_application:
        winning_reservation = winning_application.application_apartments.get(
            apartment_uuid=apartment_uuid
        ).apartment_reservation
    else:
        # There are no applications so the winning reservation is the first reservation
        # in the queue
        winning_reservation = (
            ApartmentReservation.objects.exclude(
                state=ApartmentReservationState.CANCELED
            )
            .filter(apartment_uuid=apartment_uuid)
            .order_by("queue_position")
            .first()
        )

        if not winning_reservation:
            return None

    winning_reservation.set_state(ApartmentReservationState.RESERVED)

    return winning_reservation.application_apartment


def _cancel_lower_priority_haso_applications(
    winning_applications: QuerySet,
    reserved_apartment_uuid: uuid.UUID,
) -> None:
    """
    Go through the given winning applications, and cancel each application made for
    an apartment that has a lower priority than the reserved apartment.
    Only cancel RESERVED or SUBMITTED reservations.
    The canceled application is removed from the queue of the corresponding apartment.
    """
    for app in winning_applications:
        app_apartments = app.application_apartments.all()
        priority = app_apartments.get(
            apartment_uuid=reserved_apartment_uuid
        ).priority_number
        low_priority_app_apartments = app_apartments.filter(
            priority_number__gt=priority,
            apartment_reservation__state__in=[
                ApartmentReservationState.SUBMITTED,
                ApartmentReservationState.RESERVED,
            ],
        )
        for app_apartment in low_priority_app_apartments:
            cancel_reservation(
                app_apartment.apartment_reservation,
                cancellation_reason=ApartmentReservationCancellationReason.LOWER_PRIORITY,  # noqa: E501
            )


def _find_winning_candidates(applications: QuerySet) -> QuerySet:
    """Return all applications that have the smallest right of residence number."""
    if not applications.exists():
        return applications.none()

    first_app = applications.first()
    first_app_right_of_residence = first_app.right_of_residence
    first_app_right_of_residence_is_old_batch = (
        first_app.right_of_residence_is_old_batch
    )
    return applications.filter(
        right_of_residence=first_app_right_of_residence,
        right_of_residence_is_old_batch=first_app_right_of_residence_is_old_batch,
    )
