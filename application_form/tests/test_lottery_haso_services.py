from pytest import mark

from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models.lottery import LotteryEvent, LotteryEventResult
from application_form.services.application import (
    cancel_haso_application,
    get_ordered_applications,
)
from application_form.services.lottery.haso import _distribute_haso_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import ApplicationFactory


@mark.django_db
def test_single_application_should_win_an_apartment(
    elastic_haso_project_with_5_apartments,
):
    # The single application should win the apartment
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app_apartment = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)
    # There should be exactly one winner
    assert list(get_ordered_applications(first_apartment_uuid)) == [app]
    app_apartment.refresh_from_db()
    # The application state also should have changed
    assert (
        app_apartment.apartment_reservation.state == ApartmentReservationState.RESERVED
    )


@mark.django_db
def test_application_with_the_smallest_right_of_residence_number_wins(
    elastic_haso_project_with_5_apartments,
):
    # Smallest right of residence number should win regardless of when it was
    # added to the queue.
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    winner = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    applications = [
        ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2),
        winner,
        ApplicationFactory(type=ApplicationType.HASO, right_of_residence=3),
    ]
    for app in applications:
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=0
        )
        add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)
    # The smallest right of residence number should be the winner
    assert list(get_ordered_applications(first_apartment_uuid)) == [
        winner,
        applications[0],
        applications[2],
    ]
    winner.refresh_from_db()
    # The application state also should have changed
    state = winner.application_apartments.get(
        apartment_uuid=first_apartment_uuid
    ).apartment_reservation.state
    assert state == ApartmentReservationState.RESERVED


@mark.django_db
def test_original_application_order_is_persisted_before_distribution(
    elastic_haso_project_with_5_apartments,
):
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app1 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    app3 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=3)
    applications = [app3, app1, app2]
    app_apt1 = app1.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app2.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt3 = app3.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    for app in applications:
        add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)
    # There should be an event corresponding to the apartment
    lottery_event = LotteryEvent.objects.filter(apartment_uuid=first_apartment_uuid)
    assert lottery_event.exists()
    # The current queue should have been persisted in the correct order
    results = LotteryEventResult.objects.filter(event=lottery_event.get())
    assert results.filter(result_position=1, application_apartment=app_apt1).exists()
    assert results.filter(result_position=2, application_apartment=app_apt2).exists()
    assert results.filter(result_position=3, application_apartment=app_apt3).exists()


@mark.django_db
def test_application_order_is_not_persisted_twice(
    elastic_haso_project_with_5_apartments,
):
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)
    _distribute_haso_apartments(project_uuid)
    assert LotteryEvent.objects.filter(apartment_uuid=first_apartment_uuid).count() == 1


@mark.django_db
def test_canceling_application_sets_application_state_to_canceled(
    elastic_haso_project_with_5_apartments,
):
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app_apt = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)
    cancel_haso_application(app_apt)
    app_apt.refresh_from_db()
    assert app_apt.apartment_reservation.state == ApartmentReservationState.CANCELED


@mark.django_db
def test_removing_application_from_queue_cancels_application_and_decides_new_winner(
    elastic_haso_project_with_5_apartments,
):
    # If an apartment has been reserved for an application but the application is
    # removed from the queue afterwards, the application for the apartment should
    # be marked as canceled, and the next application in the queue should become
    # the new winning candidate and marked as RESERVED.
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    old_winner = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    new_winner = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    old_winner.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    new_winner.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(old_winner)
    add_application_to_queues(new_winner)
    _distribute_haso_apartments(project_uuid)
    assert list(get_ordered_applications(first_apartment_uuid)) == [
        old_winner,
        new_winner,
    ]
    old_app_apartment = old_winner.application_apartments.get(
        apartment_uuid=first_apartment_uuid
    )
    assert (
        old_app_apartment.apartment_reservation.state
        == ApartmentReservationState.RESERVED
    )
    cancel_haso_application(old_app_apartment)
    old_app_apartment.refresh_from_db()
    assert (
        old_app_apartment.apartment_reservation.state
        == ApartmentReservationState.CANCELED
    )
    assert list(get_ordered_applications(first_apartment_uuid)) == [new_winner]
    new_app_apartment = new_winner.application_apartments.get(
        apartment_uuid=first_apartment_uuid
    )
    assert (
        new_app_apartment.apartment_reservation.state
        == ApartmentReservationState.RESERVED
    )


@mark.django_db
def test_winners_with_same_right_of_residence_number_are_marked_for_review(
    elastic_haso_project_with_5_apartments,
):
    # If there are multiple winning candidates with the same right of residence number,
    # they are still treated as "winners", but should be marked as "REVIEW".
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app1 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app3 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    app_apt1 = app1.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app2.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt3 = app3.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app1)
    add_application_to_queues(app2)
    add_application_to_queues(app3)
    _distribute_haso_apartments(project_uuid)
    assert list(get_ordered_applications(first_apartment_uuid)) == [app1, app2, app3]
    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()
    app_apt3.refresh_from_db()
    assert app_apt1.apartment_reservation.state == ApartmentReservationState.REVIEW
    assert app_apt2.apartment_reservation.state == ApartmentReservationState.REVIEW
    assert app_apt3.apartment_reservation.state == ApartmentReservationState.SUBMITTED


@mark.django_db
def test_winning_cancels_lower_priority_applications_if_not_reserved(
    elastic_haso_project_with_5_apartments,
):
    # If an application wins an apartment, all applications with lower priority
    # should be canceled, as long as that they have not been reserved already
    # for the same application and are not first in the queue.
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    second_apartment_uuid = apartments[1].uuid
    app1 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    app_apt1 = app1.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app2.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    app_apt3 = app2.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app1)
    add_application_to_queues(app2)
    _distribute_haso_apartments(project_uuid)
    assert list(get_ordered_applications(first_apartment_uuid)) == [app1]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app2]
    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()
    app_apt3.refresh_from_db()
    assert app_apt1.apartment_reservation.state == ApartmentReservationState.RESERVED
    assert app_apt2.apartment_reservation.state == ApartmentReservationState.CANCELED
    assert app_apt3.apartment_reservation.state == ApartmentReservationState.RESERVED


@mark.django_db
def test_winning_does_not_cancel_lower_priority_apartments_if_reserved(
    elastic_haso_project_with_5_apartments,
):
    # If an application wins an apartment but has already won a different apartment
    # with a lower priority, then we should not automatically cancel the reserved
    # application despite it being lower priority. This kind of situation needs to
    # be handled manually by the salesperson.
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    second_apartment_uuid = apartments[1].uuid
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app_apt1 = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=1
    )
    add_application_to_queues(app)
    app_apt2.apartment_reservation.state = ApartmentReservationState.RESERVED
    app_apt2.apartment_reservation.save(update_fields=["state"])
    _distribute_haso_apartments(project_uuid)
    assert list(get_ordered_applications(first_apartment_uuid)) == [app]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app]
    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()
    assert app_apt1.apartment_reservation.state == ApartmentReservationState.RESERVED
    assert app_apt2.apartment_reservation.state == ApartmentReservationState.RESERVED


@mark.django_db
def test_winning_does_not_cancel_lower_priority_apartments_first_in_queue(
    elastic_haso_project_with_5_apartments,
):
    # If an application wins an apartment but is also first in queue for a different
    # apartment with a lower priority, then we should not automatically cancel the
    # lower priority application. This kind of situation needs to be handled manually
    # by the salesperson.
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    second_apartment_uuid = apartments[1].uuid
    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app_apt1 = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=1
    )
    add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)
    assert list(get_ordered_applications(first_apartment_uuid)) == [app]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app]
    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()
    assert app_apt1.apartment_reservation.state == ApartmentReservationState.RESERVED
    assert app_apt2.apartment_reservation.state == ApartmentReservationState.RESERVED


@mark.django_db
def test_winning_does_not_cancel_higher_priority_applications(
    elastic_haso_project_with_5_apartments,
):
    # If an application wins an apartment with lower priority, then we should not
    # automatically cancel submitted applications for apartments with higher priority.
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    second_apartment_uuid = apartments[1].uuid
    app1 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app2 = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=2)
    app_apt1 = app1.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app2.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt3 = app2.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=1
    )
    add_application_to_queues(app1)
    add_application_to_queues(app2)
    _distribute_haso_apartments(project_uuid)
    assert list(get_ordered_applications(first_apartment_uuid)) == [app1, app2]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app2]
    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()
    app_apt3.refresh_from_db()
    assert app_apt1.apartment_reservation.state == ApartmentReservationState.RESERVED
    assert app_apt2.apartment_reservation.state == ApartmentReservationState.SUBMITTED
    assert app_apt3.apartment_reservation.state == ApartmentReservationState.RESERVED
