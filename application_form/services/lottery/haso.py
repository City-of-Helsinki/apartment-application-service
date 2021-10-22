from apartment.models import Project
from application_form.services.application import _reserve_haso_apartment
from application_form.services.lottery.utils import _save_application_order


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
