from django.db.models import QuerySet

from apartment.models import Apartment, Project
from application_form.enums import ApplicationState
from application_form.models import ApplicationApartment
from application_form.services.queue import (
    get_ordered_applications,
    remove_application_from_queue,
)


def distribute_haso_apartments(project: Project) -> None:
    """
    Declares a winner for each apartment in the project.

    This goes through each apartment in the given project, calculates the winner for
    each, and marks the winning application as reserved. Before declaring a winner, the
    state of the apartment queue will be persisted to the database.
    """
    apartments = project.apartments.all()

    # Persist the initial order of applications
    for apartment in apartments:
        _save_application_order(apartment)

    # Reserve each apartment. This will modify the queue of each apartment, since
    # apartment applications with lower priority may get canceled.
    for apartment in apartments:
        _reserve_haso_apartment(apartment)


def cancel_haso_application(application_apartment: ApplicationApartment) -> None:
    """
    Mark the application as canceled and remove it from the apartment queue.

    If the application has already won the apartment, then the winner for the apartment
    will be recalculated.
    """
    was_reserved = application_apartment.state in [
        ApplicationState.RESERVED,
        ApplicationState.REVIEW,
    ]
    apartment = application_apartment.apartment
    remove_application_from_queue(application_apartment)
    if was_reserved:
        _reserve_haso_apartment(apartment)


def _reserve_haso_apartment(apartment: Apartment) -> None:
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
    applications = get_ordered_applications(apartment)

    # There can be a single winner, or multiple winners if there are several
    # winning candidates with the same right of residence number.
    winning_applications = _find_winning_candidates(applications)

    # Set the reservation state to either "RESERVED" or "REVIEW"
    _update_reservation_state(winning_applications, apartment)

    # At this point the winner has been decided, but the winner may have outstanding
    # applications to other apartments. If they are lower priority, they should be
    # marked as "CANCELED" and deleted from the respective queues.
    _cancel_lower_priority_applications(winning_applications, apartment)


def _update_reservation_state(applications: QuerySet, apartment: Apartment) -> None:
    """
    Update the state of the apartment application to either "RESERVED" or "REVIEW",
    depending on whether there is one or more winning candidates.
    """
    application_state = ApplicationState.RESERVED
    if applications.count() > 1:
        application_state = ApplicationState.REVIEW
    for app in applications:
        app_apartment = app.application_apartments.get(apartment=apartment)
        app_apartment.state = application_state
        app_apartment.save(update_fields=["state"])


def _save_application_order(apartment: Apartment) -> None:
    """
    Persist the apartment queue for the given apartment in the database.
    This creates a new lottery event for the apartment and associates the apartment
    applications to that event in the order of their current queue position.

    If the apartment queue has already been recorded, then this function does nothing;
    a lottery is performed only once and therefore its result is stored only once.
    """
    if apartment.lottery_events.exists():
        return  # don't record it twice
    event = apartment.lottery_events.create(apartment=apartment)
    queue_applications = apartment.queue.queue_applications.all()
    for queue_application in queue_applications:
        event.results.create(
            application_apartment=queue_application.application_apartment,
            result_position=queue_application.queue_position,
        )


def _cancel_lower_priority_applications(
    winning_applications: QuerySet,
    reserved_apartment: Apartment,
) -> None:
    """
    Go through the given winning applications, and cancel each application made for
    an apartment that has a lower priority than the reserved apartment and is not in
    the first place in the queue. The canceled application is removed from the queue of
    the corresponding apartment.
    """
    for app in winning_applications:
        app_apartments = app.application_apartments.all()
        priority = app_apartments.get(apartment=reserved_apartment).priority_number
        low_priority_app_apartments = app_apartments.filter(
            priority_number__gt=priority,
            state=ApplicationState.SUBMITTED,
            queue_application__queue_position__gt=0,
        )
        for app_apartment in low_priority_app_apartments:
            cancel_haso_application(app_apartment)


def _find_winning_candidates(applications: QuerySet) -> QuerySet:
    """Return all applications that have the smallest right of residence number."""
    if not applications.exists():
        return applications.none()
    min_right_of_residence = applications.first().right_of_residence
    return applications.filter(right_of_residence=min_right_of_residence)
