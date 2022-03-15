import uuid

from apartment.elastic.queries import get_apartment_uuids
from application_form.services.application import _reserve_haso_apartment
from application_form.services.lottery.utils import _save_application_order


def _distribute_haso_apartments(project_uuid: uuid.UUID) -> None:
    """
    Declares a winner for each apartment in the project.

    This goes through each apartment in the given project, calculates the winner for
    each, and marks the winning application as reserved. Before declaring a winner, the
    state of the apartment queue will be persisted to the database.
    """
    apartment_uuids = get_apartment_uuids(project_uuid)

    # Persist the initial order of applications
    for apartment_uuid in apartment_uuids:
        _save_application_order(apartment_uuid)

    # Reserve each apartment. This will modify the queue of each apartment, since
    # apartment applications with lower priority may get canceled.
    for apartment_uuid in apartment_uuids:
        _reserve_haso_apartment(apartment_uuid)
