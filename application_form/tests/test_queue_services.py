import logging
from unittest.mock import Mock

from django.db.models import QuerySet
from pytest import mark, raises

from apartment.enums import OwnershipType
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

    assert caplog.records[0].levelname == "WARNING"
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
