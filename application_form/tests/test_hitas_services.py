from pytest import mark
from unittest.mock import patch

from apartment.tests.factories import ApartmentFactory, ProjectFactory
from application_form.enums import ApplicationState, ApplicationType
from application_form.models import LotteryEventResult
from application_form.services.hitas import (
    cancel_hitas_application,
    distribute_hitas_apartments,
)
from application_form.services.queue import (
    add_application_to_queues,
    get_ordered_applications,
)
from application_form.tests.factories import ApplicationFactory


@mark.django_db
def test_single_application_should_win_an_apartment():
    # The single application should win the apartment
    apt = ApartmentFactory()
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apartment = app.application_apartments.create(apartment=apt, priority_number=0)
    add_application_to_queues(app)
    distribute_hitas_apartments(apt.project)
    # The only applicant should have won the apartment
    assert list(get_ordered_applications(apt)) == [app]
    app_apartment.refresh_from_db()
    # The application state also should have changed
    assert app_apartment.state == ApplicationState.RESERVED


@mark.django_db
def test_lottery_for_small_apartment_does_not_prioritize_applications_with_children():
    # Applications with children should not be prioritized if the apartment is small

    # Small apartment, so children should not matter
    apt = ApartmentFactory(room_count=2)

    # Single person applies to the apartment
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_app = single.application_apartments.create(apartment=apt, priority_number=0)
    add_application_to_queues(single)

    # Family applies to the same apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(apartment=apt, priority_number=0)
    add_application_to_queues(family)

    # Either the family or the single applicant can win the apartment,
    # so the shuffling needs to be mocked to get deterministic results.
    with patch("secrets.randbelow", return_value=0):
        distribute_hitas_apartments(apt.project)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The single person should have been randomly picked as the winner
    assert list(get_ordered_applications(apt)) == [single, family]
    # The application state also should have changed
    assert single_app.state == ApplicationState.RESERVED
    # The loser's state should have stayed the same
    assert family_app.state == ApplicationState.SUBMITTED


@mark.django_db
def test_lottery_for_large_apartment_prioritizes_applications_with_children():
    # Large apartment, so children should be taken into account
    apt = ApartmentFactory(room_count=10)

    # Single person applies to the apartment
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_app = single.application_apartments.create(apartment=apt, priority_number=0)
    add_application_to_queues(single)

    # Family applies to the same apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(apartment=apt, priority_number=0)
    add_application_to_queues(family)

    # Decide the winner
    distribute_hitas_apartments(apt.project)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The family should have been picked as the winner
    assert list(get_ordered_applications(apt)) == [family, single]
    # The application state also should have changed
    assert family_app.state == ApplicationState.RESERVED
    # The loser's state should have stayed the same
    assert single_app.state == ApplicationState.SUBMITTED


@mark.django_db
def test_lottery_result_is_persisted_before_apartment_distribution():
    apt = ApartmentFactory()
    applications = [
        ApplicationFactory(type=ApplicationType.HITAS),
        ApplicationFactory(type=ApplicationType.HITAS),
        ApplicationFactory(type=ApplicationType.HITAS),
    ]
    for app in applications:
        app.application_apartments.create(apartment=apt, priority_number=0)
        add_application_to_queues(app)

    # Deciding the winner should trigger the queue to be recorded
    distribute_hitas_apartments(apt.project)

    # There should be an event corresponding to the apartment
    lottery_event = apt.lottery_events
    assert lottery_event.exists()

    # The current queue should have been persisted
    results = LotteryEventResult.objects.filter(event=lottery_event.get())
    assert results.count() == len(applications)

    # Each position should appear in the results exactly once
    for position in range(len(applications)):
        assert results.filter(result_position=position).count() == 1

    # Each application should appear in the results exactly once
    for app in applications:
        assert results.filter(application_apartment__application=app).count() == 1


@mark.django_db
def test_lottery_result_is_not_persisted_twice():
    apartment = ApartmentFactory()
    application = ApplicationFactory(type=ApplicationType.HITAS)
    application.application_apartments.create(apartment=apartment, priority_number=0)
    add_application_to_queues(application)
    distribute_hitas_apartments(apartment.project)
    distribute_hitas_apartments(apartment.project)  # Should not record another event
    assert apartment.lottery_events.count() == 1


@mark.django_db
def test_canceling_application_sets_state_to_canceled():
    apartment = ApartmentFactory()
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apt = app.application_apartments.create(apartment=apartment, priority_number=0)
    add_application_to_queues(app)

    # This will mark the application for the apartment as "RESERVED"
    distribute_hitas_apartments(apartment.project)

    # Cancel the application for the apartment
    cancel_hitas_application(app_apt)

    # The state should now be "CANCELED"
    app_apt.refresh_from_db()
    assert app_apt.state == ApplicationState.CANCELED


@mark.django_db
def test_canceling_winning_application_marks_next_application_in_queue_as_reserved():
    # If an application has won an apartment, but the application is canceled
    # afterwards, the next application in the queue should become the new winner and
    # should be marked as "RESERVED".

    # Large apartment, a family is guaranteed to win it
    apartment = ApartmentFactory(room_count=10)

    # An applicant who will later reject the apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(
        apartment=apartment, priority_number=0
    )
    add_application_to_queues(family)

    # An applicant who will first place second in the queue, but will become the winner
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_app = single.application_apartments.create(
        apartment=apartment, priority_number=0
    )
    add_application_to_queues(single)

    # Decide the result
    distribute_hitas_apartments(apartment.project)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The family winner should win the apartment
    assert list(get_ordered_applications(apartment)) == [family, single]
    assert family_app.state == ApplicationState.RESERVED

    # The family rejects the apartment
    cancel_hitas_application(family_app)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The family should have been removed from the queue, and the other application
    # should have become the new winner.
    assert list(get_ordered_applications(apartment)) == [single]
    assert family_app.state == ApplicationState.CANCELED
    assert single_app.state == ApplicationState.RESERVED


@mark.django_db
def test_becoming_first_after_lottery_does_not_cancel_low_priority_reservation():
    project = ProjectFactory()

    # Two apartments, one big and one tiny. The single applicant will try to get the
    # bigger apartment with higher priority.
    big = ApartmentFactory(project=project, room_count=10)
    tiny = ApartmentFactory(project=project, room_count=1)

    # A family that applies to the first apartment and will win it with children
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_big = family.application_apartments.create(apartment=big, priority_number=0)
    add_application_to_queues(family)

    # A single applicant who applies to both apartments, the big one with high priority
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_big = single.application_apartments.create(apartment=big, priority_number=0)
    single_tiny = single.application_apartments.create(
        apartment=tiny, priority_number=1
    )
    add_application_to_queues(single)

    # Perform lottery
    distribute_hitas_apartments(project)

    family_big.refresh_from_db()
    single_big.refresh_from_db()
    single_tiny.refresh_from_db()

    # The family should have won the big apartment
    assert list(get_ordered_applications(big)) == [family, single]
    assert family_big.state == ApplicationState.RESERVED

    # The single applicant's low priority application should be "RESERVED"
    assert list(get_ordered_applications(tiny)) == [single]
    assert single_tiny.state == ApplicationState.RESERVED

    # The family later rejects the big apartment
    cancel_hitas_application(family_big)

    # The queue for the tiny apartment should have stayed the same, and
    # the reserved application should not have been canceled.
    assert list(get_ordered_applications(tiny)) == [single]
    single_tiny.refresh_from_db()
    assert single_tiny.state == ApplicationState.RESERVED

    # The single applicant should be be the winner of the big apartment
    assert list(get_ordered_applications(big)) == [single]
    single_big.refresh_from_db()
    assert single_big.state == ApplicationState.RESERVED


@mark.django_db
def test_winning_high_priority_apartment_cancels_lower_priority_applications():
    # If an application wins an apartment, then we should automatically cancel
    # the lower priority applications.
    project = ProjectFactory()

    # Two random apartments
    apt1 = ApartmentFactory(project=project)
    apt2 = ApartmentFactory(project=project)

    # An application that applies to both apartments
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apt1 = app.application_apartments.create(apartment=apt1, priority_number=0)
    app_apt2 = app.application_apartments.create(apartment=apt2, priority_number=1)
    add_application_to_queues(app)

    # The application should be in queue for both apartments
    assert list(get_ordered_applications(apt1)) == [app]
    assert list(get_ordered_applications(apt2)) == [app]

    # Decide the result
    distribute_hitas_apartments(project)

    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()

    # The application should be number one in the first priority apartment
    assert list(get_ordered_applications(apt1)) == [app]
    assert app_apt1.state == ApplicationState.RESERVED

    # The second application should have been removed from the queue
    assert list(get_ordered_applications(apt2)) == []
    assert app_apt2.state == ApplicationState.CANCELED


@mark.django_db
def test_winning_high_priority_apartment_redistributes_apartments_if_winner_changed():
    # If an application wins an apartment, then we should automatically cancel
    # the lower priority applications. Note that when canceling an application,
    # the winner of an apartment can change, so the cancelation logic should be
    # able to handle that.

    project = ProjectFactory()

    # Three apartments
    apt1 = ApartmentFactory(project=project, room_count=1)
    apt2 = ApartmentFactory(project=project, room_count=1)
    apt3 = ApartmentFactory(project=project, room_count=1)

    # Application 1 applies to each apartment with priorities 0, 1, 2
    app1 = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    app1_apt1 = app1.application_apartments.create(apartment=apt1, priority_number=0)
    app1_apt2 = app1.application_apartments.create(apartment=apt2, priority_number=1)
    app1_apt3 = app1.application_apartments.create(apartment=apt3, priority_number=2)
    app1_apts = [app1_apt1, app1_apt2, app1_apt3]
    add_application_to_queues(app1)

    # Application 2 applies to each apartment with priorities 1, 2, 0
    app2 = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    app2_apt1 = app2.application_apartments.create(apartment=apt1, priority_number=1)
    app2_apt2 = app2.application_apartments.create(apartment=apt2, priority_number=2)
    app2_apt3 = app2.application_apartments.create(apartment=apt3, priority_number=0)
    app2_apts = [app2_apt1, app2_apt2, app2_apt3]
    add_application_to_queues(app2)

    # Application 3 applies to each apartment with priorities 0, 1, 2
    app3 = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    app3_apt1 = app3.application_apartments.create(apartment=apt1, priority_number=0)
    app3_apt2 = app3.application_apartments.create(apartment=apt2, priority_number=1)
    app3_apt3 = app3.application_apartments.create(apartment=apt3, priority_number=2)
    app3_apts = [app3_apt1, app3_apt2, app3_apt3]
    add_application_to_queues(app3)

    assert list(get_ordered_applications(apt1)) == [app1, app2, app3]
    assert list(get_ordered_applications(apt2)) == [app1, app2, app3]
    assert list(get_ordered_applications(apt2)) == [app1, app2, app3]

    # Decide the result. We need a predictable result here, so the queue positions
    # will be determined based on the application order.
    with patch("secrets.randbelow", return_value=0):
        distribute_hitas_apartments(project)

    assert list(get_ordered_applications(apt1)) == [app1, app3]
    assert list(get_ordered_applications(apt2)) == [app3]
    assert list(get_ordered_applications(apt3)) == [app2]

    for app_apt in app1_apts + app2_apts + app3_apts:
        app_apt.refresh_from_db()

    # All the winners should have been marked as "RESERVED"
    assert app1_apt1.state == ApplicationState.RESERVED
    assert app3_apt2.state == ApplicationState.RESERVED
    assert app2_apt3.state == ApplicationState.RESERVED

    # All the canceled applications should have been marked as "CANCELED"
    assert app1_apt2.state == ApplicationState.CANCELED
    assert app1_apt3.state == ApplicationState.CANCELED
    assert app2_apt1.state == ApplicationState.CANCELED
    assert app2_apt2.state == ApplicationState.CANCELED
    assert app3_apt3.state == ApplicationState.CANCELED


@mark.django_db
def test_winning_low_priority_apartment_does_not_cancel_higher_priority_applications():
    # If an application wins an apartment with lower priority, then we should not
    # automatically cancel submitted applications for apartments with higher priority.
    project = ProjectFactory()

    # Two apartments, one big and one tiny
    big = ApartmentFactory(project=project, room_count=10)
    tiny = ApartmentFactory(project=project, room_count=1)

    # A family that applies only to the first apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(apartment=big, priority_number=0)
    add_application_to_queues(family)

    # A single applicant who applies to both apartments
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_high = single.application_apartments.create(apartment=big, priority_number=0)
    single_low = single.application_apartments.create(apartment=tiny, priority_number=1)
    add_application_to_queues(single)

    # Decide the result
    distribute_hitas_apartments(project)

    family_app.refresh_from_db()
    single_high.refresh_from_db()
    single_low.refresh_from_db()

    # The family should have won the big apartment
    assert list(get_ordered_applications(big)) == [family, single]
    assert family_app.state == ApplicationState.RESERVED

    # The single applicant should win the second apartment at low priority
    assert list(get_ordered_applications(tiny)) == [single]
    assert single_low.state == ApplicationState.RESERVED

    # The other application should still be in the queue, since it was higher priority
    assert single_high.state == ApplicationState.SUBMITTED
