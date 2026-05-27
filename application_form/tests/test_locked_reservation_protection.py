"""
Regression tests for the bug where a SOLD reservation got downgraded to RESERVED
when winner-recalculation ran on the apartment.

Production incident (2026-05-17):

A HASO customer submitted a late application ("jälkihakemus"). The late-application
flow in `ApplicationSerializerBase.create` cancels the customer's prior reservations
on other apartments in the same project. Each cancel calls
`_reserve_haso_apartment(apt_uuid)` for the apartment whose reservation was canceled.
That function unconditionally called `set_state(RESERVED)` on the queue-head
application, which downgraded the existing SOLD reservation on the apartment.

These tests pin down the invariant: winner recalculation must never auto-downgrade
a sold reservation. Manual state changes via the sales UI are still allowed.
"""

from unittest.mock import MagicMock, patch

from django.urls import reverse
from pytest import fixture, mark

from apartment.enums import OwnershipType
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models import ApartmentReservation, Application
from application_form.services.application import (
    _reserve_apartment,
    _reserve_haso_apartment,
    cancel_reservation,
)
from application_form.services.lottery.haso import _distribute_haso_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.conftest import create_application_data, generate_apartments
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@fixture(autouse=True)
def check_latest_reservation_state_change_events_after_every_test(
    check_latest_reservation_state_change_events,
):
    pass


def _build_haso_winner_with_runner_up(
    apartment_uuid,
    winner_state: ApartmentReservationState,
    *,
    winner_right_of_residence: int = 1,
    runner_up_right_of_residence: int = 2,
):
    """
    Create a HASO apartment queue with a queue-position-1 winner already moved to
    `winner_state`, and a queue-position-2 runner-up in RESERVED state.

    Returns (winner_reservation, runner_up_reservation).
    """
    winner_reservation = ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.RESERVED,
        application_apartment__application__type=ApplicationType.HASO,
        application_apartment__application__right_of_residence=(
            winner_right_of_residence
        ),
        application_apartment__application__right_of_residence_is_old_batch=False,
    )
    runner_up_reservation = ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        queue_position=2,
        list_position=2,
        state=ApartmentReservationState.RESERVED,
        application_apartment__application__type=ApplicationType.HASO,
        application_apartment__application__right_of_residence=(
            runner_up_right_of_residence
        ),
        application_apartment__application__right_of_residence_is_old_batch=False,
    )
    LotteryEventFactory.create(apartment_uuid=apartment_uuid)
    winner_reservation.set_state(winner_state)
    return winner_reservation, runner_up_reservation


@mark.django_db
def test_reserve_haso_apartment_does_not_downgrade_sold_winner(
    elastic_haso_project_with_5_apartments,
):
    """
    Calling `_reserve_haso_apartment` on an apartment whose queue-head reservation
    is already SOLD must not downgrade that reservation.
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    winner, _runner_up = _build_haso_winner_with_runner_up(
        apartment_uuid, ApartmentReservationState.SOLD
    )
    events_before = winner.state_change_events.count()

    _reserve_haso_apartment(apartment_uuid)

    winner.refresh_from_db()
    assert winner.state == ApartmentReservationState.SOLD, (
        "SOLD winner was downgraded by _reserve_haso_apartment"
    )
    assert winner.state_change_events.count() == events_before, (
        "No new state-change event should be created for the sold winner"
    )


@mark.django_db
def test_reserve_apartment_hitas_does_not_downgrade_sold_winner(
    elastic_hitas_project_with_5_apartments,
):
    """
    Same invariant for HITAS: `_reserve_apartment` must not downgrade a queue-head
    reservation that is already SOLD.
    """
    _, apartments = elastic_hitas_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    winner = ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.RESERVED,
        application_apartment__application__type=ApplicationType.HITAS,
    )
    ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        queue_position=2,
        list_position=2,
        state=ApartmentReservationState.RESERVED,
        application_apartment__application__type=ApplicationType.HITAS,
    )
    LotteryEventFactory.create(apartment_uuid=apartment_uuid)
    winner.set_state(ApartmentReservationState.SOLD)
    events_before = winner.state_change_events.count()

    _reserve_apartment(apartment_uuid)

    winner.refresh_from_db()
    assert winner.state == ApartmentReservationState.SOLD, (
        "SOLD HITAS winner was downgraded by _reserve_apartment"
    )
    assert winner.state_change_events.count() == events_before, (
        "No new state-change event should be created for the sold winner"
    )


@mark.django_db
def test_cancel_reservation_in_same_apartment_does_not_downgrade_sold_winner_haso(
    elastic_haso_project_with_5_apartments,
):
    """
    Reproduces the production trigger directly: a non-SUBMITTED reservation behind
    the SOLD winner is canceled. `cancel_reservation` calls
    `_reserve_haso_apartment` because `was_reserved=True`, and that call must not
    downgrade the SOLD reservation.
    """
    _, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    sold_winner, runner_up = _build_haso_winner_with_runner_up(
        apartment_uuid, ApartmentReservationState.SOLD
    )
    events_before = sold_winner.state_change_events.count()

    cancel_reservation(
        runner_up,
        cancellation_reason=ApartmentReservationCancellationReason.CANCELED,
    )

    sold_winner.refresh_from_db()
    assert sold_winner.state == ApartmentReservationState.SOLD, (
        "Cancelling a reservation behind a SOLD winner must not downgrade "
        "the SOLD reservation"
    )
    assert sold_winner.state_change_events.count() == events_before, (
        "No new state-change event should be created for the SOLD reservation"
    )


@mark.django_db
def test_distribute_haso_apartments_is_idempotent_after_sale(
    elastic_haso_project_with_5_apartments,
):
    """
    Re-running the lottery on a HASO project that already has SOLD apartments must
    not regress the sold reservations to RESERVED.
    """
    project_uuid, apartments = elastic_haso_project_with_5_apartments
    apartment_uuid = apartments[0].uuid

    app = ApplicationFactory(type=ApplicationType.HASO, right_of_residence=1)
    app.application_apartments.create(
        apartment_uuid=apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)
    _distribute_haso_apartments(project_uuid)

    reservation = ApartmentReservation.objects.get(
        apartment_uuid=apartment_uuid,
        application_apartment__application=app,
    )
    reservation.set_state(ApartmentReservationState.OFFERED)
    reservation.set_state(ApartmentReservationState.OFFER_ACCEPTED)
    reservation.set_state(ApartmentReservationState.SOLD)
    events_before = reservation.state_change_events.count()

    _distribute_haso_apartments(project_uuid)

    reservation.refresh_from_db()
    assert reservation.state == ApartmentReservationState.SOLD, (
        "Re-running HASO lottery must not downgrade SOLD reservations"
    )
    assert reservation.state_change_events.count() == events_before, (
        "Re-running lottery must not produce a new state-change event on a "
        "sold reservation"
    )


@mark.django_db
@patch("application_form.services.application.EmailMessage", new_callable=MagicMock)
def test_late_haso_application_does_not_downgrade_sold_winner_in_other_apartment(
    EmailMessageMock,
    drupal_server_api_client,
    elasticsearch,
):
    """
    End-to-end regression for the production incident: a customer submits a HASO
    late application. The late-application flow cancels the customer's prior
    reservations on apartments not included in the new late application. If one of
    those prior reservations sat behind another customer's SOLD reservation, the
    SOLD reservation must not be downgraded.
    """
    haso_project_properties = {
        "project_ownership_type": OwnershipType.HASO.value,
        "project_can_apply_afterwards": True,
        "project_housing_company": "Haso Nihdinlaituri Test",
        "project_estate_agent_email": "agent@example.com",
        "_language": "fi",
    }
    apartments = generate_apartments(elasticsearch, 3, haso_project_properties)
    sold_apartment, customer_y_only_apartment, late_target_apartment = apartments

    # Buyer (Customer X) wins and is sold the first apartment.
    buyer = ApplicationFactory(
        type=ApplicationType.HASO,
        right_of_residence=1,
        right_of_residence_is_old_batch=False,
    )
    buyer.application_apartments.create(
        apartment_uuid=sold_apartment.uuid, priority_number=0
    )
    add_application_to_queues(buyer)
    _distribute_haso_apartments(sold_apartment.project_uuid)
    sold_reservation = ApartmentReservation.objects.get(
        apartment_uuid=sold_apartment.uuid,
        application_apartment__application=buyer,
    )
    sold_reservation.set_state(ApartmentReservationState.OFFERED)
    sold_reservation.set_state(ApartmentReservationState.OFFER_ACCEPTED)
    sold_reservation.set_state(ApartmentReservationState.SOLD)

    # Customer Y had an on-time application covering both the now-sold apartment
    # and one other apartment. Their reservation on the sold apartment is at
    # queue position 2 (behind the SOLD winner).
    customer_y_profile = ProfileFactory()
    customer_y_application = ApplicationFactory(
        type=ApplicationType.HASO,
        right_of_residence=99,
        right_of_residence_is_old_batch=False,
        customer__primary_profile=customer_y_profile,
    )
    customer_y_application.application_apartments.create(
        apartment_uuid=sold_apartment.uuid, priority_number=0
    )
    customer_y_application.application_apartments.create(
        apartment_uuid=customer_y_only_apartment.uuid, priority_number=1
    )
    add_application_to_queues(customer_y_application)
    _distribute_haso_apartments(sold_apartment.project_uuid)
    # Customer Y won the other apartment, so that reservation is in RESERVED.
    # Their reservation on the sold apartment sits behind the SOLD winner.
    customer_y_reservation_on_sold = ApartmentReservation.objects.get(
        apartment_uuid=sold_apartment.uuid,
        application_apartment__application=customer_y_application,
    )
    assert customer_y_reservation_on_sold.state == ApartmentReservationState.SUBMITTED
    # Promote to RESERVED to mirror the production state (this is the realistic
    # case where the cancel cascade fires `_reserve_haso_apartment` because
    # `was_reserved=True`).
    customer_y_reservation_on_sold.set_state(ApartmentReservationState.RESERVED)

    sold_reservation.refresh_from_db()
    assert sold_reservation.state == ApartmentReservationState.SOLD
    sold_events_before = sold_reservation.state_change_events.count()

    # Customer Y now submits a late application for a different apartment in the
    # same project. The late-application flow will cancel their prior reservations
    # on the sold apartment and on `customer_y_only_apartment`.
    drupal_server_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(customer_y_profile)}"
    )
    late_data = create_application_data(
        customer_y_profile,
        application_type=ApplicationType.HASO,
        num_applicants=1,
        apartments=[late_target_apartment],
    )
    response = drupal_server_api_client.post(
        reverse("application_form:application-list"), late_data, format="json"
    )
    assert response.status_code == 201, response.content
    new_application = Application.objects.get(
        external_uuid=response.json()["application_uuid"]
    )
    assert new_application.submitted_late is True

    # Customer Y's prior reservation on the sold apartment must be CANCELED.
    customer_y_reservation_on_sold.refresh_from_db()
    assert (
        customer_y_reservation_on_sold.state == ApartmentReservationState.CANCELED
    )

    # The actual regression assertion: the unrelated SOLD reservation on the same
    # apartment must NOT have been downgraded by the cancel cascade.
    sold_reservation.refresh_from_db()
    assert sold_reservation.state == ApartmentReservationState.SOLD, (
        "Late application's cancel cascade downgraded a SOLD reservation on "
        "another apartment in the project"
    )
    assert sold_reservation.state_change_events.count() == sold_events_before, (
        "No new state-change event should be written on the SOLD reservation"
    )
