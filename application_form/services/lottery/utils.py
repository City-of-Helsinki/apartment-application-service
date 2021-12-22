from apartment.models import Apartment


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
    queue_applications = apartment.queue_applications.all()
    for queue_application in queue_applications:
        event.results.create(
            application_apartment=queue_application.application_apartment,
            result_position=queue_application.queue_position,
        )
