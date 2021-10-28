from django.db.models import QuerySet
from pytest import mark, raises
from unittest.mock import Mock

from apartment.tests.factories import ApartmentFactory
from application_form.enums import ApartmentQueueChangeEventType, ApplicationType
from application_form.models import ApartmentQueue, ApartmentQueueChangeEvent
from application_form.services.application import get_ordered_applications
from application_form.services.queue import (
    add_application_to_queues,
    remove_application_from_queue,
)
from application_form.tests.factories import ApplicationFactory


@mark.django_db
def test_get_ordered_applications_returns_empty_queryset_when_no_applications():
    # If an apartment has no queue, it shouldn't crash but return an empty QS instead
    applications = get_ordered_applications(ApartmentFactory())
    assert isinstance(applications, QuerySet)
    assert applications.count() == 0


@mark.django_db
def test_get_ordered_applications_returns_applications_sorted_by_position():
    # Regardless of the right of residence number of the applications in a queue,
    # they should be returned sorted by their position in the queue.
    apartment = ApartmentFactory()
    app1 = ApplicationFactory()
    app2 = ApplicationFactory()
    app3 = ApplicationFactory()
    applications = [app3, app1, app2]
    queue = ApartmentQueue.objects.create(apartment=apartment)
    for position, app in enumerate(applications):
        app_apartment = app.application_apartments.create(
            apartment=apartment, priority_number=1
        )
        queue.queue_applications.create(
            queue_position=position, application_apartment=app_apartment
        )
    # Should be sorted by queue position
    assert list(get_ordered_applications(apartment)) == applications


@mark.django_db
def test_adding_application_raises_exception_if_type_is_unsupported():
    # An exception should be raised if we try to add an application with type other
    # than HASO, HITAS, or PUOLIHITAS into the queue.
    bad_application_type = Mock(ApplicationType)
    bad_application_type.value = "unknown"

    app = ApplicationFactory(right_of_residence=1)
    app.type = bad_application_type
    app.application_apartments.create(apartment=ApartmentFactory(), priority_number=1)
    with raises(ValueError):
        add_application_to_queues(app)


@mark.django_db
def test_add_haso_application_to_queue_is_based_on_right_of_residence_number():
    # HASO applications should be added to the queue based
    # on their right of residence number.
    apartment = ApartmentFactory()
    app1 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    app3 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=3)
    applications = [app3, app1, app2]
    for app in applications:
        app.application_apartments.create(apartment=apartment, priority_number=1)
        add_application_to_queues(app)
    # Should be sorted by queue position which is decided by right of residence number
    assert list(get_ordered_applications(apartment)) == [app1, app2, app3]


@mark.django_db
def test_add_hitas_application_to_queue_is_based_on_addition_order():
    # HITAS applications should be ordered by their addition order
    apartment = ApartmentFactory()
    app1 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=2)
    app3 = ApplicationFactory(type=ApplicationType.HITAS, right_of_residence=3)
    applications = [app3, app1, app2]
    for app in applications:
        app.application_apartments.create(apartment=apartment, priority_number=1)
        add_application_to_queues(app)
    # Should be sorted by queue position which is decided by the order they were added
    assert list(get_ordered_applications(apartment)) == applications


@mark.django_db
def test_add_late_application_ignores_right_of_residence_number():
    # Late applications should be added to the end of the queue,
    # even if they have a smaller right of residence number.
    apartment = ApartmentFactory()
    applications = [
        ApplicationFactory(right_of_residence=2),
        ApplicationFactory(right_of_residence=3),
    ]
    for app in applications:
        app.application_apartments.create(apartment=apartment, priority_number=1)
        add_application_to_queues(app)
    late_app = ApplicationFactory(right_of_residence=1, submitted_late=True)
    late_app.application_apartments.create(apartment=apartment, priority_number=1)
    add_application_to_queues(late_app)
    # The late application should be last despite its smallest right of residence number
    assert list(get_ordered_applications(apartment)) == applications + [late_app]


@mark.django_db
def test_add_late_application_remains_at_end_when_new_application_is_added():
    # Applications added late should remain at the end of the queue ordered by
    # the right of residence numbers.
    apartment = ApartmentFactory()
    apps = [
        ApplicationFactory(type=ApplicationType.HASO, right_of_residence=3),
        ApplicationFactory(type=ApplicationType.HASO, right_of_residence=4),
    ]
    for app in apps:
        app.application_apartments.create(apartment=apartment, priority_number=1)
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
        late_app.application_apartments.create(apartment=apartment, priority_number=1)
        add_application_to_queues(late_app)
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app.application_apartments.create(apartment=apartment, priority_number=1)
    add_application_to_queues(app)
    # The application should be added to the top and
    # the previous one should stay at the bottom.
    assert list(get_ordered_applications(apartment)) == [app] + apps + [
        late_app1,
        late_app2,
        late_app3,
    ]


@mark.django_db
def test_adding_application_to_queue_creates_change_event():
    # If an application is added manually to the queue, we want to create a change
    # event with a comment.
    apartment = ApartmentFactory()
    application = ApplicationFactory(right_of_residence=1)
    application.application_apartments.create(apartment=apartment, priority_number=1)
    change_comment = "Added manually."
    add_application_to_queues(application, comment=change_comment)
    # An "ADDED" change event with comment should have been created
    assert ApartmentQueueChangeEvent.objects.filter(
        queue_application__queue=apartment.queue,
        type=ApartmentQueueChangeEventType.ADDED,
        comment=change_comment,
    ).exists()


@mark.django_db
def test_remove_application_from_queue():
    # An application should be removed from the queue and all remaining applications
    # should be moved up by one position each.
    apartment = ApartmentFactory()
    applications = [
        ApplicationFactory(right_of_residence=1),
        ApplicationFactory(right_of_residence=2),
        ApplicationFactory(right_of_residence=3),
    ]
    queue = ApartmentQueue.objects.create(apartment=apartment)
    for position, app in enumerate(applications):
        app_apartment = app.application_apartments.create(
            apartment=apartment, priority_number=1
        )
        queue.queue_applications.create(
            queue_position=position, application_apartment=app_apartment
        )
    apartment_application = applications[0].application_apartments.get(
        apartment=apartment
    )
    remove_application_from_queue(apartment_application)
    # The application should have been removed from the first place in the queue
    assert list(get_ordered_applications(apartment)) == applications[1:]


@mark.django_db
def test_removing_application_from_queue_creates_change_event():
    # If an application is removed manually from the queue, we want to create a change
    # event with a comment.
    apartment = ApartmentFactory()
    application = ApplicationFactory(right_of_residence=1)
    application.application_apartments.create(apartment=apartment, priority_number=1)
    add_application_to_queues(application)
    change_comment = "Removed manually."
    apartment_application = application.application_apartments.get(apartment=apartment)
    remove_application_from_queue(apartment_application, comment=change_comment)
    # A "REMOVED" change event with comment should have been created
    assert ApartmentQueueChangeEvent.objects.filter(
        queue_application__queue=apartment.queue,
        type=ApartmentQueueChangeEventType.REMOVED,
        comment=change_comment,
    ).exists()
