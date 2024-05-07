import secrets
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet

from apartment.elastic.queries import get_apartment, get_apartment_uuids
from application_form.models import ApplicationApartment
from application_form.services.application import _reserve_apartments
from application_form.services.lottery.utils import _save_application_order

User = get_user_model()
# If the number of rooms in an apartment is greater or equal to this threshold,
# then applications with children are prioritized in the lottery process.
_PRIORITIZE_CHILDREN_ROOM_THRESHOLD = 3


def _distribute_hitas_apartments(project_uuid: uuid.UUID, user: User = None) -> None:
    """
    Declares a winner for each apartment in the project.

    This goes through each apartment in the given project, calculates the winner for
    each, and marks the winning application as reserved. Before declaring a winner, the
    state of the apartment queue will be persisted to the database.
    """

    apartment_uuids = get_apartment_uuids(project_uuid)

    # Perform lottery and persist the initial order of applications
    for apartment_uuid in apartment_uuids:
        _shuffle_applications(apartment_uuid)
        _save_application_order(apartment_uuid, user)

    _reserve_apartments(apartment_uuids)


def _shuffle_applications(apartment_uuid: uuid.UUID) -> None:
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
    apartment = get_apartment(apartment_uuid)
    apartment_apps = ApplicationApartment.objects.filter(apartment_uuid=apartment_uuid)
    if not apartment_apps:
        return
    # If the apartment has enough rooms, applications with children should have priority
    prioritize_children = apartment.room_count >= _PRIORITIZE_CHILDREN_ROOM_THRESHOLD
    if prioritize_children:
        # Split applications into two pools
        apps_with_children = apartment_apps.filter(application__has_children=True)
        apps_without_children = apartment_apps.exclude(application__has_children=True)
        with transaction.atomic():
            # The first queue segment go to applications with children, in random order
            _shuffle_queue_segment(apps_with_children)
            # The remaining segment go to applications without children
            _shuffle_queue_segment(
                apps_without_children, apps_with_children.count() + 1
            )
    else:
        # Each application stays in the same pool and is assigned a random position
        _shuffle_queue_segment(apartment_apps)


@transaction.atomic
def _shuffle_queue_segment(
    application_apartments: QuerySet,
    start_position: int = 1,
) -> None:
    """
    Randomizes the queue segment of the given applications, starting at the given
    position. A unique queue position between start_position (inclusive) and
    start_position + number of application apartments (exclusive) will be assigned
    randomly for each application in the queue.
    """
    end_position = start_position + application_apartments.count()

    # Create a list of all possible queue positions between start and end position
    possible_positions = list(range(start_position, end_position))

    for app_apartment in application_apartments.order_by("id").all():
        # Remove a random queue position from the list assign it to the application
        random_index = secrets.randbelow(len(possible_positions))
        position = possible_positions.pop(random_index)
        apartment_reservation = app_apartment.apartment_reservation
        apartment_reservation.list_position = position
        apartment_reservation.queue_position = position
        apartment_reservation.save(update_fields=["list_position", "queue_position"])
