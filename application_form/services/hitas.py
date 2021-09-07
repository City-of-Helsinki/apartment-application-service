import secrets
from django.db import transaction
from django.db.models import QuerySet
from typing import Iterable, List, Optional

from apartment.models import Apartment, Project
from application_form.enums import ApplicationState
from application_form.models import ApplicationApartment
from application_form.services.queue import (
    get_ordered_applications,
    remove_application_from_queue,
)

# If the number of rooms in an apartment is greater or equal to this threshold,
# then applications with children are prioritized in the lottery process.
_PRIORITIZE_CHILDREN_ROOM_THRESHOLD = 3


def distribute_hitas_apartments(project: Project) -> None:
    apartments = project.apartments.all()

    # Perform lottery and persist the initial order of applications
    for apartment in apartments:
        _shuffle_applications(apartment)
        _save_application_order(apartment)

    _reserve_apartments(apartments)


def cancel_hitas_application(application_apartment: ApplicationApartment) -> None:
    """
    Cancel a HITAS application for a specific apartment. If the application has already
    won an apartment, then the winner for that apartment must be recalculated.
    """
    apartment = application_apartment.apartment
    was_reserved = application_apartment.state in [
        ApplicationState.RESERVED,
        ApplicationState.OFFERED,
    ]
    remove_application_from_queue(application_apartment)
    if was_reserved:
        _reserve_apartments([apartment], False)


def _reserve_apartments(
    apartments: Iterable[Apartment],
    cancel_lower_priority_reserved: bool = True,
) -> None:
    apartments_to_process = set(list(apartments))
    while apartments_to_process:
        for apartment in apartments_to_process.copy():
            apartments_to_process.remove(apartment)
            # Mark the winner as "RESERVED"
            winner = _update_reservation(apartment)
            if winner is None:
                continue
            # If the winner has lower priority applications, we should cancel them.
            # This will modify the queues of other apartments, and if the apartment's
            # winner gets canceled, that apartment must be processed again.
            canceled_winners = _cancel_lower_priority_applications(
                winner, cancel_lower_priority_reserved
            )
            apartments_to_process.update(app.apartment for app in canceled_winners)


def _update_reservation(apartment: Apartment) -> Optional[ApplicationApartment]:
    # The winning application is whoever is at first position in the queue
    winning_application = get_ordered_applications(apartment).first()
    if winning_application is None:
        return None
    app_apartment = winning_application.application_apartments.get(apartment=apartment)
    app_apartment.state = ApplicationState.RESERVED
    app_apartment.save(update_fields=["state"])
    return app_apartment


def _shuffle_applications(apartment: Apartment) -> None:
    """
    Randomize the order of the applications to the given apartment.

    The shuffling method depends on the number of rooms in the apartment. For small
    apartments, the queue positions are randomized between all applications. For large
    apartments, applications with children are prioritized.

    If the apartment is large, the applications are divided to two pools, one for the
    applications with children, and another one for the applications without children.
    The first positions in the apartment queue will go to applications with children, in
    random order. The remaining positions will go to the applications without children,
    in random order.
    """
    apartment_apps = apartment.application_apartments

    # If the apartment has enough rooms, applications with children should have priority
    prioritize_children = apartment.room_count >= _PRIORITIZE_CHILDREN_ROOM_THRESHOLD
    if prioritize_children:
        # Split applications into two pools
        apps_with_children = apartment_apps.filter(application__has_children=True)
        apps_without_children = apartment_apps.exclude(application__has_children=True)
        with transaction.atomic():
            # The first positions go to applications with children, in random order
            _shuffle_queue_positions(apps_with_children)
            # The remaining positions go to applications without children
            _shuffle_queue_positions(apps_without_children, apps_with_children.count())
    else:
        # Each application stays in the same pool and is assigned a random position
        _shuffle_queue_positions(apartment_apps)


@transaction.atomic
def _shuffle_queue_positions(
    application_apartments: QuerySet,
    start_position: int = 0,
) -> None:
    """
    Randomizes the queue positions of the given applications, starting at the given
    position. A unique queue position between start_position (inclusive) and
    start_position + number of application apartments (exclusive) will be assigned
    randomly for each application in the queue.
    """
    end_position = start_position + application_apartments.count() - 1

    # Create a list of all possible queue positions between start and end position
    possible_positions = list(range(start_position, end_position + 1))

    for app_apartment in application_apartments.all():
        # Remove a random queue position from the list assign it to the application
        random_index = secrets.randbelow(len(possible_positions))
        position = possible_positions.pop(random_index)
        queue_application = app_apartment.queue_application
        queue_application.queue_position = position
        queue_application.save(update_fields=["queue_position"])


def _save_application_order(apartment: Apartment) -> None:
    """
    Persists the apartment queue for the given apartment in the database.
    This creates a new lottery events for the apartment and adds applications
    to that event in the order of their current queue position.

    If the apartment queue has already been recorded, then this function does nothing.
    """
    if apartment.lottery_events.exists():
        return
    event = apartment.lottery_events.create(apartment=apartment)
    queue_applications = apartment.queue.queue_applications.all()
    for queue_application in queue_applications:
        event.results.create(
            application_apartment=queue_application.application_apartment,
            result_position=queue_application.queue_position,
        )


def _cancel_lower_priority_applications(
    application_apartment: ApplicationApartment,
    cancel_reserved: bool = True,
) -> List[ApplicationApartment]:
    """
    Given the winning apartment application, cancel each apartment application for the
    same project that has a lower priority than the reserved apartment, no matter what
    position they are in the queue. The canceled application is removed from the queue
    of the corresponding apartment.
    """
    states_to_cancel = [ApplicationState.SUBMITTED]
    if cancel_reserved:
        states_to_cancel.append(ApplicationState.RESERVED)
    app_apartments = application_apartment.application.application_apartments.all()
    lower_priority_app_apartments = app_apartments.filter(
        priority_number__gt=application_apartment.priority_number,
        state__in=states_to_cancel,
    )
    canceled_winners = []
    for app_apartment in lower_priority_app_apartments:
        if app_apartment.queue_application.queue_position == 0:
            canceled_winners.append(app_apartment)
        cancel_hitas_application(app_apartment)
    return canceled_winners
