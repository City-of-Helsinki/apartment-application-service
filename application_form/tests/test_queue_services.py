import logging
from unittest.mock import Mock

from django.db.models import QuerySet
from pytest import mark, raises

from apartment.elastic.queries import get_apartment
from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models.reservation import (
    ApartmentQueueChangeEvent,
    ApartmentReservation,
)
from application_form.services.application import get_ordered_applications
from application_form.services.queue import (
    add_application_to_queues,
    remove_queue_gaps,
    remove_reservation_from_queue,
)
from application_form.tests.conftest import generate_apartments, sell_apartments
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationFactory,
)
from customer.tests.factories import CustomerFactory


@mark.django_db
def test_new_reservation_wont_override_first_one_if_asu_1802(elasticsearch):
    """
    When haso reservation has state OFFERED, SOLD or OFFER ACCEPTED then adding
    a new reservation with a lower right of residence number shouldn't override it.
    """

    apartments = generate_apartments(
        elasticsearch,
        apartment_count=1,
        apartment_kwargs={
            "project_ownership_type": OwnershipType.HASO.value,
        },
    )
    sold_apartment = apartments[0]
    sell_apartments(sold_apartment.project_uuid, 1)

    original_first_reservation = ApartmentReservation.objects.filter(
        apartment_uuid=sold_apartment.uuid, queue_position=1
    ).first()
    original_first_reservation_pk = original_first_reservation.pk
    # now create reservation with lower right of residence number
    new_application_right_of_residence = (
        original_first_reservation.right_of_residence - 10
    )

    customer = CustomerFactory()
    new_application = ApplicationFactory(
        type=ApplicationType.HASO,
        customer=customer,
        has_children=False,
        right_of_residence=new_application_right_of_residence,
    )

    new_application.application_apartments.create(
        apartment_uuid=sold_apartment.uuid, priority_number=1
    )
    add_application_to_queues(new_application)

    assert (
        ApartmentReservation.objects.get(
            queue_position=1, apartment_uuid=sold_apartment.uuid
        ).pk
        == original_first_reservation_pk
    )


def _add_haso_application_to_queue(
    apartment_uuid,
    *,
    right_of_residence,
    submitted_late=False,
    state=None,
):
    """
    Create a HASO application, add it to the apartment queue, and optionally
    move the resulting reservation to ``state``.
    """
    application = ApplicationFactory(
        type=ApplicationType.HASO,
        right_of_residence=right_of_residence,
        submitted_late=submitted_late,
    )
    application.application_apartments.create(
        apartment_uuid=apartment_uuid, priority_number=1
    )
    add_application_to_queues(application)
    reservation = application.application_apartments.get(
        apartment_uuid=apartment_uuid
    ).apartment_reservation
    if state is not None:
        reservation.set_state(state)
    return application, reservation


@mark.parametrize(
    "protected_state",
    (
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_EXPIRED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY,
        ApartmentReservationState.SOLD,
    ),
)
@mark.django_db
def test_late_haso_application_does_not_jump_already_offered_reservation(
    elastic_haso_project_with_5_apartments,
    protected_state,
):
    """
    Late HASO applications must not take queue position 1 from a reservation
    that has already been offered.

    Production incident (Nihdinlaituri A10): a late application jumped to
    position 1 while the current winner was in OFFER_EXPIRED
    ("tarjous vanhentunut").

    - Existing late reservation at position 1 is in a post-offer state
    - A SUBMITTED late reservation sits behind it
    - New late application has a better (lower) right of residence number
    - The offered reservation stays at position 1
    - The new reservation is inserted after it, before the SUBMITTED one
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    offered_app, offered_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=500,
        submitted_late=True,
        state=protected_state,
    )
    submitted_app, submitted_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=800,
        submitted_late=True,
    )

    new_app, new_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=100,
        submitted_late=True,
    )

    offered_reservation.refresh_from_db()
    submitted_reservation.refresh_from_db()
    new_reservation.refresh_from_db()

    assert offered_reservation.queue_position == 1
    assert new_reservation.queue_position == 2
    assert submitted_reservation.queue_position == 3
    assert list(get_ordered_applications(apartment_uuid)) == [
        offered_app,
        new_app,
        submitted_app,
    ]


@mark.django_db
def test_haso_application_does_not_jump_offer_expired_on_time_reservation(
    elastic_haso_project_with_5_apartments,
):
    """
    On-time HASO applications must not jump an OFFER_EXPIRED queue head.

    - Existing on-time reservation at position 1 is OFFER_EXPIRED
    - New on-time application has a better (lower) right of residence number
    - OFFER_EXPIRED reservation stays at position 1
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    offered_app, offered_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=500,
        submitted_late=False,
        state=ApartmentReservationState.OFFER_EXPIRED,
    )

    new_app, new_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=100,
        submitted_late=False,
    )

    offered_reservation.refresh_from_db()
    new_reservation.refresh_from_db()

    assert offered_reservation.queue_position == 1
    assert new_reservation.queue_position == 2
    assert list(get_ordered_applications(apartment_uuid)) == [offered_app, new_app]


@mark.parametrize(
    "protected_state",
    (
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_EXPIRED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY,
        ApartmentReservationState.SOLD,
    ),
)
@mark.django_db
def test_late_haso_application_does_not_pass_offered_reservation_behind_queue_head(
    elastic_haso_project_with_5_apartments,
    protected_state,
):
    """
    An already offered reservation must not be passed even when it is not the
    queue head.

    - SUBMITTED late reservation at position 1, offered one at position 2
    - New late application has the best right of residence number
    - Both existing reservations keep their positions
    - New reservation goes behind the offered one
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    submitted_app, submitted_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=500,
        submitted_late=True,
    )
    offered_app, offered_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=800,
        submitted_late=True,
        state=protected_state,
    )

    new_app, new_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=100,
        submitted_late=True,
    )

    submitted_reservation.refresh_from_db()
    offered_reservation.refresh_from_db()
    new_reservation.refresh_from_db()

    assert submitted_reservation.queue_position == 1
    assert offered_reservation.queue_position == 2
    assert new_reservation.queue_position == 3
    assert list(get_ordered_applications(apartment_uuid)) == [
        submitted_app,
        offered_app,
        new_app,
    ]


@mark.django_db
def test_late_haso_application_does_not_pass_salesperson_created_offered_reservation(
    elastic_haso_project_with_5_apartments,
):
    """
    Offered reservations without an application are protected too.

    Salesperson-created reservations have no linked application, so they are
    invisible to the right of residence scan and can only be protected through
    the queue floor.

    - Salesperson-created OFFER_EXPIRED reservation holds position 1
    - New late application has the best right of residence number
    - The offered reservation keeps position 1
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    offered_reservation = ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        application_apartment=None,
        queue_position=1,
        list_position=1,
        submitted_late=True,
        right_of_residence=500,
        right_of_residence_is_old_batch=False,
        state=ApartmentReservationState.OFFER_EXPIRED,
    )

    _, new_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=100,
        submitted_late=True,
    )

    offered_reservation.refresh_from_db()
    new_reservation.refresh_from_db()

    assert offered_reservation.queue_position == 1
    assert new_reservation.queue_position == 2


@mark.django_db
def test_late_haso_application_still_orders_among_submitted_late_reservations(
    elastic_haso_project_with_5_apartments,
):
    """
    Late HASO applications must still be ordered by right of residence among
    other late reservations that have not been offered.

    - Two SUBMITTED late reservations exist
    - New late application has a right of residence between them
    - New reservation is inserted between the two SUBMITTED ones
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    first_app, first_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=200,
        submitted_late=True,
    )
    second_app, second_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=800,
        submitted_late=True,
    )

    new_app, new_reservation = _add_haso_application_to_queue(
        apartment_uuid,
        right_of_residence=400,
        submitted_late=True,
    )

    first_reservation.refresh_from_db()
    second_reservation.refresh_from_db()
    new_reservation.refresh_from_db()

    assert first_reservation.queue_position == 1
    assert new_reservation.queue_position == 2
    assert second_reservation.queue_position == 3
    assert list(get_ordered_applications(apartment_uuid)) == [
        first_app,
        new_app,
        second_app,
    ]


@mark.django_db
def test_get_ordered_applications_returns_empty_queryset_when_no_applications(
    elastic_project_with_5_apartments,
):
    # If an apartment has no queue, it shouldn't crash but return an empty QS instead
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    applications = get_ordered_applications(first_apartment_uuid)
    assert isinstance(applications, QuerySet)
    assert applications.count() == 0


@mark.django_db
def test_get_ordered_applications_returns_applications_sorted_by_position(
    elastic_project_with_5_apartments,
):
    # Regardless of the right of residence number of the applications in a queue,
    # they should be returned sorted by their position in the queue.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app1 = ApplicationFactory()
    app2 = ApplicationFactory()
    app3 = ApplicationFactory()
    applications = [app3, app1, app2]
    for position, application in enumerate(applications):
        application_apartment = application.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        ApartmentReservation.objects.create(
            customer=application_apartment.application.customer,
            queue_position=position,
            list_position=position,
            application_apartment=application_apartment,
            apartment_uuid=first_apartment_uuid,
        )
    # Should be sorted by queue position
    assert list(get_ordered_applications(first_apartment_uuid)) == applications


@mark.django_db
def test_adding_application_raises_exception_if_type_is_unsupported(
    elastic_project_with_5_apartments,
):
    # An exception should be raised if we try to add an application with type other
    # than HASO, HITAS, or PUOLIHITAS into the queue.
    bad_application_type = Mock(ApplicationType)
    bad_application_type.value = "unknown"

    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid

    app = ApplicationFactory(right_of_residence=1)
    app.type = bad_application_type
    app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    with raises(ValueError):
        add_application_to_queues(app)


@mark.django_db
def test_add_haso_application_to_queue_is_based_on_right_of_residence_number(
    elastic_project_with_5_apartments,
):
    # HASO applications should be added to the queue based
    # on their right of residence number.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app1 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    app3 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=3)
    applications = [app3, app1, app2]
    for app in applications:
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        add_application_to_queues(app)
    # Should be sorted by queue position which is decided by right of residence number
    assert list(get_ordered_applications(first_apartment_uuid)) == [app1, app2, app3]


@mark.django_db
def test_add_hitas_application_to_queue_is_based_on_addition_order(
    elastic_project_with_5_apartments,
):
    # HITAS applications should be ordered by their addition order
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app1 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=2)
    app3 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=3)
    applications = [app3, app1, app2]
    for app in applications:
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        add_application_to_queues(app)
    # Should be sorted by queue position which is decided by the order they were added
    assert list(get_ordered_applications(first_apartment_uuid)) == applications


@mark.django_db
def test_add_late_application_ignores_right_of_residence_number(
    elastic_project_with_5_apartments,
):
    # Late applications should be added to the end of the queue,
    # even if they have a smaller right of residence number.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    applications = [
        ApplicationFactory(right_of_residence=2),
        ApplicationFactory(right_of_residence=3),
    ]
    for app in applications:
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        add_application_to_queues(app)
    late_app = ApplicationFactory(right_of_residence=1, submitted_late=True)
    late_app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    add_application_to_queues(late_app)
    # The late application should be last despite its smallest right of residence number
    assert list(get_ordered_applications(first_apartment_uuid)) == applications + [
        late_app
    ]


@mark.django_db
def test_add_late_application_remains_at_end_when_new_application_is_added(
    elastic_project_with_5_apartments,
):
    # Applications added late should remain at the end of the queue ordered by
    # the right of residence numbers.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    apps = [
        ApplicationFactory(type=ApplicationType.HASO, right_of_residence=3),
        ApplicationFactory(type=ApplicationType.HASO, right_of_residence=4),
    ]
    for app in apps:
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        add_application_to_queues(app)
    late_apps = [
        ApplicationFactory(
            type=ApplicationType.HASO, right_of_residence=6, submitted_late=True
        ),
        ApplicationFactory(
            type=ApplicationType.HASO, right_of_residence=2, submitted_late=True
        ),
        ApplicationFactory(
            type=ApplicationType.HASO, right_of_residence=5, submitted_late=True
        ),
    ]
    late_app3, late_app1, late_app2 = late_apps
    for late_app in late_apps:
        late_app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        add_application_to_queues(late_app)
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    add_application_to_queues(app)
    # The application should be added to the top and
    # the previous one should stay at the bottom.
    assert list(get_ordered_applications(first_apartment_uuid)) == [app] + apps + [
        late_app1,
        late_app2,
        late_app3,
    ]


@mark.django_db
def test_adding_application_to_queue_creates_change_event(
    elastic_project_with_5_apartments,
):
    # If an application is added manually to the queue, we want to create a change
    # event with a comment.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    application = ApplicationFactory(right_of_residence=1)
    application.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    change_comment = "Added manually."
    add_application_to_queues(application, comment=change_comment)
    # An "ADDED" change event with comment should have been created
    assert ApartmentQueueChangeEvent.objects.filter(
        queue_application__apartment_uuid=first_apartment_uuid,
        type=ApartmentQueueChangeEventType.ADDED,
        comment=change_comment,
    ).exists()


@mark.django_db
def test_remove_application_from_queue(elastic_project_with_5_apartments):
    # An application should be removed from the queue and all remaining applications
    # should be moved up by one position each.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    applications = [
        ApplicationFactory(right_of_residence=1),
        ApplicationFactory(right_of_residence=2),
        ApplicationFactory(right_of_residence=3),
    ]
    for position, application in enumerate(applications):
        application_apartment = application.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        ApartmentReservation.objects.create(
            customer=application_apartment.application.customer,
            queue_position=position,
            list_position=position,
            application_apartment=application_apartment,
            apartment_uuid=first_apartment_uuid,
        )
    apartment_application = applications[0].application_apartments.get(
        apartment_uuid=first_apartment_uuid
    )
    remove_reservation_from_queue(apartment_application.apartment_reservation)
    # The application should have been removed from the first place in the queue
    assert list(get_ordered_applications(first_apartment_uuid)) == applications[1:]


@mark.django_db
def test_removing_application_from_queue_creates_change_event(
    elastic_project_with_5_apartments,
):
    # If an application is removed manually from the queue, we want to create a change
    # event with a comment.
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    application = ApplicationFactory(right_of_residence=1)
    application.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    add_application_to_queues(application)
    change_comment = "Removed manually."
    apartment_application = application.application_apartments.get(
        apartment_uuid=first_apartment_uuid
    )
    remove_reservation_from_queue(
        apartment_application.apartment_reservation, comment=change_comment
    )
    # A "REMOVED" change event with comment should have been created
    assert ApartmentQueueChangeEvent.objects.filter(
        queue_application__apartment_uuid=first_apartment_uuid,
        type=ApartmentQueueChangeEventType.REMOVED,
        comment=change_comment,
    ).exists()


@mark.django_db
def test_removing_application_from_queue_nullifies_queue_number(
    elastic_project_with_5_apartments,
):
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    application = ApplicationFactory(right_of_residence=1)
    application.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    add_application_to_queues(application)
    apartment_application = application.application_apartments.get(
        apartment_uuid=first_apartment_uuid
    )
    remove_reservation_from_queue(apartment_application.apartment_reservation)

    apartment_application.apartment_reservation.refresh_from_db()

    assert apartment_application.apartment_reservation.queue_position is None


@mark.django_db
def test_remove_reservation_without_queue_positio_bug_ASU_1672(
    elastic_project_with_5_apartments, caplog
):
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    reservation = ApartmentReservationFactory(
        apartment_uuid=first_apartment_uuid, queue_position=None
    )

    with caplog.at_level(logging.INFO, logger="application_form.services.queue"):
        remove_reservation_from_queue(reservation)

    assert any(
        record.levelname == "WARNING"
        and record.name == "application_form.services.queue"
        for record in caplog.records
    )
    assert first_apartment_uuid in caplog.text


@mark.django_db
def test_add_hitas_application_to_queue_with_only_cancelled_reservations(
    elastic_project_with_5_apartments,
):
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app1 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=1)
    app1.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    ApartmentReservationFactory(
        apartment_uuid=first_apartment_uuid,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
    )

    # this used to raise an exception
    add_application_to_queues(app1)

    assert (
        ApartmentReservation.objects.active()
        .filter(apartment_uuid=first_apartment_uuid)
        .first()
        .queue_position
        == 1
    )


@mark.django_db
def test_add_haso_application_to_queue_with_a_cancelled_reservation(
    elastic_project_with_5_apartments,
):
    """
    Test that a HASO application can be added to the queue even though
    the queue has a cancelled reservation.
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=42)
    app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    ApartmentReservationFactory(
        apartment_uuid=first_apartment_uuid,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
    )

    # this used to raise an exception
    add_application_to_queues(app)

    assert (
        ApartmentReservation.objects.active()
        .filter(apartment_uuid=first_apartment_uuid)
        .first()
        .queue_position
        == 1
    )


@mark.parametrize("application_type", (ApplicationType.HITAS, ApplicationType.HASO))
@mark.django_db
def test_remove_queue_gaps(elastic_project_with_5_apartments, application_type):
    apartment = ApartmentDocumentFactory()
    first_apartment_uuid = apartment.uuid

    # create some applications+reservations
    # add gaps in queue_positions (missing 1., 3., 6. and 7.)
    gap_indexes = [0, 2, 5, 6]
    reservations = []

    for idx in range(12):
        app = ApplicationFactory(type=application_type, right_of_residence=idx)
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=1
        )
        if idx in gap_indexes:
            continue

        reservations.append(
            ApartmentReservationFactory(
                apartment_uuid=first_apartment_uuid,
                state=ApartmentReservationState.SUBMITTED,
                queue_position=idx + 1,
                list_position=idx + 1,
            )
        )

    # if list_position is out of order, can get unique_together constraint errors
    # swap two indexes to cause this out of orderness for test
    res = reservations[6]
    res.list_position = 1
    res.save()

    # assert there are no gaps in queue positions
    remove_queue_gaps(get_apartment(first_apartment_uuid))

    reservation_queue_positions = (
        ApartmentReservation.objects.filter(apartment_uuid=first_apartment_uuid)
        .order_by("queue_position")
        .values_list("queue_position", flat=True)
    )

    last_idx = len(reservation_queue_positions) - 1

    for idx, qp in enumerate(reservation_queue_positions):
        if idx == last_idx:
            continue

        next_qp = reservation_queue_positions[idx + 1]
        assert next_qp == qp + 1
