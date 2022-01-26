from pytest import mark
from unittest.mock import patch

from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models import LotteryEvent, LotteryEventResult
from application_form.services.application import (
    cancel_hitas_application,
    get_ordered_applications,
)
from application_form.services.lottery.hitas import distribute_hitas_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import ApplicationFactory


@mark.django_db
def test_single_application_should_win_an_apartment(
    elastic_hitas_project_with_5_apartments,
):
    # The single application should win the apartment
    project_uuid, apartments = elastic_hitas_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apartment = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)
    distribute_hitas_apartments(project_uuid)
    # The only applicant should have won the apartment
    assert list(get_ordered_applications(first_apartment_uuid)) == [app]
    app_apartment.refresh_from_db()
    # The application state also should have changed
    assert (
        app_apartment.apartment_reservation.state == ApartmentReservationState.RESERVED
    )


@mark.django_db
def test_lottery_for_small_apartment_does_not_prioritize_applications_with_children(
    elastic_hitas_project_with_apartment_room_count_2,
):
    # Applications with children should not be prioritized if the apartment is small

    # Small apartment, so children should not matter
    project_uuid, apartment = elastic_hitas_project_with_apartment_room_count_2

    # Single person applies to the apartment
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_app = single.application_apartments.create(
        apartment_uuid=apartment.uuid, priority_number=0
    )
    add_application_to_queues(single)

    # Family applies to the same apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(
        apartment_uuid=apartment.uuid, priority_number=0
    )
    add_application_to_queues(family)

    # Either the family or the single applicant can win the apartment,
    # so the shuffling needs to be mocked to get deterministic results.
    with patch("secrets.randbelow", return_value=0):
        distribute_hitas_apartments(project_uuid)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The single person should have been randomly picked as the winner
    assert list(get_ordered_applications(apartment.uuid)) == [single, family]
    # The application state also should have changed
    assert single_app.apartment_reservation.state == ApartmentReservationState.RESERVED
    # The loser's state should have stayed the same
    assert family_app.apartment_reservation.state == ApartmentReservationState.SUBMITTED


@mark.django_db
def test_lottery_for_large_apartment_prioritizes_applications_with_children(
    elastic_hitas_project_with_apartment_room_count_10,
):
    # Large apartment, so children should be taken into account
    project_uuid, apartment = elastic_hitas_project_with_apartment_room_count_10

    # Single person applies to the apartment
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_app = single.application_apartments.create(
        apartment_uuid=apartment.uuid, priority_number=0
    )
    add_application_to_queues(single)

    # Family applies to the same apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(
        apartment_uuid=apartment.uuid, priority_number=0
    )
    add_application_to_queues(family)

    # Decide the winner
    distribute_hitas_apartments(project_uuid)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The family should have been picked as the winner
    assert list(get_ordered_applications(apartment.uuid)) == [family, single]
    # The application state also should have changed
    assert family_app.apartment_reservation.state == ApartmentReservationState.RESERVED
    # The loser's state should have stayed the same
    assert single_app.apartment_reservation.state == ApartmentReservationState.SUBMITTED


@mark.django_db
def test_lottery_result_is_persisted_before_apartment_distribution(
    elastic_hitas_project_with_5_apartments,
):
    project_uuid, apartments = elastic_hitas_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    applications = [
        ApplicationFactory(type=ApplicationType.HITAS),
        ApplicationFactory(type=ApplicationType.HITAS),
        ApplicationFactory(type=ApplicationType.HITAS),
    ]
    for app in applications:
        app.application_apartments.create(
            apartment_uuid=first_apartment_uuid, priority_number=0
        )
        add_application_to_queues(app)

    # Deciding the winner should trigger the queue to be recorded
    distribute_hitas_apartments(project_uuid)

    # There should be an event corresponding to the apartment
    lottery_event = LotteryEvent.objects.filter(apartment_uuid=first_apartment_uuid)
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
def test_lottery_result_is_not_persisted_twice(elastic_hitas_project_with_5_apartments):
    project_uuid, apartments = elastic_hitas_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    application = ApplicationFactory(type=ApplicationType.HITAS)
    application.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(application)
    distribute_hitas_apartments(project_uuid)
    distribute_hitas_apartments(project_uuid)  # Should not record another event
    assert LotteryEvent.objects.filter(apartment_uuid=first_apartment_uuid).count() == 1


@mark.django_db
def test_canceling_application_sets_state_to_canceled(
    elastic_hitas_project_with_5_apartments,
):
    project_uuid, apartments = elastic_hitas_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apt = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)

    # This will mark the application for the apartment as "RESERVED"
    distribute_hitas_apartments(project_uuid)

    # Cancel the application for the apartment
    cancel_hitas_application(app_apt)

    # The state should now be "CANCELED"
    app_apt.refresh_from_db()
    assert app_apt.apartment_reservation.state == ApartmentReservationState.CANCELED


@mark.django_db
def test_canceling_winning_application_marks_next_application_in_queue_as_reserved(
    elastic_hitas_project_with_apartment_room_count_10,
):
    # If an application has won an apartment, but the application is canceled
    # afterwards, the next application in the queue should become the new winner and
    # should be marked as "RESERVED".

    # Large apartment, a family is guaranteed to win it
    (
        project_uuid,
        apartment,
    ) = elastic_hitas_project_with_apartment_room_count_10

    # An applicant who will later reject the apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(
        apartment_uuid=apartment.uuid, priority_number=0
    )
    add_application_to_queues(family)

    # An applicant who will first place second in the queue, but will become the winner
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_app = single.application_apartments.create(
        apartment_uuid=apartment.uuid, priority_number=0
    )
    add_application_to_queues(single)

    # Decide the result
    distribute_hitas_apartments(project_uuid)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The family winner should win the apartment
    assert list(get_ordered_applications(apartment.uuid)) == [family, single]
    assert family_app.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The family rejects the apartment
    cancel_hitas_application(family_app)

    family_app.refresh_from_db()
    single_app.refresh_from_db()

    # The family should have been removed from the queue, and the other application
    # should have become the new winner.
    assert list(get_ordered_applications(apartment.uuid)) == [single]
    assert family_app.apartment_reservation.state == ApartmentReservationState.CANCELED
    assert single_app.apartment_reservation.state == ApartmentReservationState.RESERVED


@mark.django_db
def test_becoming_first_after_lottery_does_not_cancel_low_priority_reservation(
    elastic_hitas_project_with_tiny_and_big_apartment,
):
    # Two apartments, one big and one tiny. The single applicant will try to get the
    # bigger apartment with higher priority.
    (
        project_uuid,
        tiny_apartment,
        big_apartment,
    ) = elastic_hitas_project_with_tiny_and_big_apartment

    # A family that applies to the first apartment and will win it with children
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_big = family.application_apartments.create(
        apartment_uuid=big_apartment.uuid, priority_number=0
    )
    add_application_to_queues(family)

    # A single applicant who applies to both apartments, the big one with high priority
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_big = single.application_apartments.create(
        apartment_uuid=big_apartment.uuid, priority_number=0
    )
    single_tiny = single.application_apartments.create(
        apartment_uuid=tiny_apartment.uuid, priority_number=1
    )
    add_application_to_queues(single)

    # Perform lottery
    distribute_hitas_apartments(project_uuid)

    family_big.refresh_from_db()
    single_big.refresh_from_db()
    single_tiny.refresh_from_db()

    # The family should have won the big apartment
    assert list(get_ordered_applications(big_apartment.uuid)) == [family, single]
    assert family_big.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The single applicant's low priority application should be "RESERVED"
    assert list(get_ordered_applications(tiny_apartment.uuid)) == [single]
    assert single_tiny.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The family later rejects the big apartment
    cancel_hitas_application(family_big)

    # The queue for the tiny apartment should have stayed the same, and
    # the reserved application should not have been canceled.
    assert list(get_ordered_applications(tiny_apartment.uuid)) == [single]
    single_tiny.refresh_from_db()
    assert single_tiny.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The single applicant should be be the winner of the big apartment
    assert list(get_ordered_applications(big_apartment.uuid)) == [single]
    single_big.refresh_from_db()
    assert single_big.apartment_reservation.state == ApartmentReservationState.RESERVED


@mark.django_db
def test_winning_high_priority_apartment_cancels_lower_priority_applications(
    elastic_hitas_project_with_5_apartments,
):
    # If an application wins an apartment, then we should automatically cancel
    # the lower priority applications.

    # Two random apartments
    project_uuid, apartments = elastic_hitas_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    second_apartment_uuid = apartments[1].uuid

    # An application that applies to both apartments
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apt1 = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app_apt2 = app.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=1
    )
    add_application_to_queues(app)

    # The application should be in queue for both apartments
    assert list(get_ordered_applications(first_apartment_uuid)) == [app]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app]

    # Decide the result
    distribute_hitas_apartments(project_uuid)

    app_apt1.refresh_from_db()
    app_apt2.refresh_from_db()

    # The application should be number one in the first priority apartment
    assert list(get_ordered_applications(first_apartment_uuid)) == [app]
    assert app_apt1.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The second application should have been removed from the queue
    assert list(get_ordered_applications(second_apartment_uuid)) == []
    assert app_apt2.apartment_reservation.state == ApartmentReservationState.CANCELED


@mark.django_db
def test_winning_high_priority_apartment_redistributes_apartments_if_winner_changed(
    elastic_hitas_project_with_3_tiny_apartments,
):
    # If an application wins an apartment, then we should automatically cancel
    # the lower priority applications. Note that when canceling an application,
    # the winner of an apartment can change, so the cancelation logic should be
    # able to handle that.

    # Three apartments
    project_uuid, apartments = elastic_hitas_project_with_3_tiny_apartments
    first_apartment_uuid = apartments[0].uuid
    second_apartment_uuid = apartments[1].uuid
    third_apartment_uuid = apartments[2].uuid

    # Application 1 applies to each apartment with priorities 0, 1, 2
    app1 = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    app1_apt1 = app1.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app1_apt2 = app1.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=1
    )
    app1_apt3 = app1.application_apartments.create(
        apartment_uuid=third_apartment_uuid, priority_number=2
    )
    app1_apts = [app1_apt1, app1_apt2, app1_apt3]
    add_application_to_queues(app1)

    # Application 2 applies to each apartment with priorities 1, 2, 0
    app2 = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    app2_apt1 = app2.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=1
    )
    app2_apt2 = app2.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=2
    )
    app2_apt3 = app2.application_apartments.create(
        apartment_uuid=third_apartment_uuid, priority_number=0
    )
    app2_apts = [app2_apt1, app2_apt2, app2_apt3]
    add_application_to_queues(app2)

    # Application 3 applies to each apartment with priorities 0, 1, 2
    app3 = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    app3_apt1 = app3.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    app3_apt2 = app3.application_apartments.create(
        apartment_uuid=second_apartment_uuid, priority_number=1
    )
    app3_apt3 = app3.application_apartments.create(
        apartment_uuid=third_apartment_uuid, priority_number=2
    )
    app3_apts = [app3_apt1, app3_apt2, app3_apt3]
    add_application_to_queues(app3)

    assert list(get_ordered_applications(first_apartment_uuid)) == [app1, app2, app3]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app1, app2, app3]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app1, app2, app3]

    # Decide the result. We need a predictable result here, so the queue positions
    # will be determined based on the application order.
    with patch("secrets.randbelow", return_value=0):
        distribute_hitas_apartments(project_uuid)

    assert list(get_ordered_applications(first_apartment_uuid)) == [app1, app3]
    assert list(get_ordered_applications(second_apartment_uuid)) == [app3]
    assert list(get_ordered_applications(third_apartment_uuid)) == [app2]

    for app_apt in app1_apts + app2_apts + app3_apts:
        app_apt.refresh_from_db()

    # All the winners should have been marked as "RESERVED"
    assert app1_apt1.apartment_reservation.state == ApartmentReservationState.RESERVED
    assert app3_apt2.apartment_reservation.state == ApartmentReservationState.RESERVED
    assert app2_apt3.apartment_reservation.state == ApartmentReservationState.RESERVED

    # All the canceled applications should have been marked as "CANCELED"
    assert app1_apt2.apartment_reservation.state == ApartmentReservationState.CANCELED
    assert app1_apt3.apartment_reservation.state == ApartmentReservationState.CANCELED
    assert app2_apt1.apartment_reservation.state == ApartmentReservationState.CANCELED
    assert app2_apt2.apartment_reservation.state == ApartmentReservationState.CANCELED
    assert app3_apt3.apartment_reservation.state == ApartmentReservationState.CANCELED


@mark.django_db
def test_winning_low_priority_apartment_does_not_cancel_higher_priority_applications(
    elastic_hitas_project_with_tiny_and_big_apartment,
):
    # If an application wins an apartment with lower priority, then we should not
    # automatically cancel submitted applications for apartments with higher priority.

    # Two apartments, one big and one tiny
    (
        project_uuid,
        tiny_apartment,
        big_apartment,
    ) = elastic_hitas_project_with_tiny_and_big_apartment

    # A family that applies only to the first apartment
    family = ApplicationFactory(type=ApplicationType.HITAS, has_children=True)
    family_app = family.application_apartments.create(
        apartment_uuid=big_apartment.uuid, priority_number=0
    )
    add_application_to_queues(family)

    # A single applicant who applies to both apartments
    single = ApplicationFactory(type=ApplicationType.HITAS, has_children=False)
    single_high = single.application_apartments.create(
        apartment_uuid=big_apartment.uuid, priority_number=0
    )
    single_low = single.application_apartments.create(
        apartment_uuid=tiny_apartment.uuid, priority_number=1
    )
    add_application_to_queues(single)

    # Decide the result
    distribute_hitas_apartments(project_uuid)

    family_app.refresh_from_db()
    single_high.refresh_from_db()
    single_low.refresh_from_db()

    # The family should have won the big apartment
    assert list(get_ordered_applications(big_apartment.uuid)) == [family, single]
    assert family_app.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The single applicant should win the second apartment at low priority
    assert list(get_ordered_applications(tiny_apartment.uuid)) == [single]
    assert single_low.apartment_reservation.state == ApartmentReservationState.RESERVED

    # The other application should still be in the queue, since it was higher priority
    assert (
        single_high.apartment_reservation.state == ApartmentReservationState.SUBMITTED
    )
