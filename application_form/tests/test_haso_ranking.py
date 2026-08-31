from types import SimpleNamespace

from pytest import mark

from application_form.enums import ApartmentReservationState
from application_form.services.haso_ranking import (
    find_haso_insert_target,
    is_protected_from_queue_jump,
    protected_queue_floor,
)


def _reservation(queue_position, ordering_number, state=None):
    """Build a minimal stand-in for ApartmentReservation."""
    return SimpleNamespace(
        queue_position=queue_position,
        right_of_residence_ordering_number=ordering_number,
        state=state or ApartmentReservationState.SUBMITTED,
    )


@mark.parametrize(
    "state",
    (
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_EXPIRED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY,
        ApartmentReservationState.SOLD,
    ),
)
def test_is_protected_from_queue_jump_accepts_enum_and_value(state):
    """
    Protected states are recognized both as enum members and as raw values.

    - Enum member is protected
    - The matching database value string is protected
    """
    assert is_protected_from_queue_jump(state) is True
    assert is_protected_from_queue_jump(state.value) is True


@mark.parametrize(
    "state",
    (
        ApartmentReservationState.SUBMITTED,
        ApartmentReservationState.RESERVED,
        ApartmentReservationState.RESERVATION_AGREEMENT,
        ApartmentReservationState.REVIEW,
        ApartmentReservationState.CANCELED,
    ),
)
def test_is_protected_from_queue_jump_leaves_pre_offer_states_jumpable(state):
    """
    States before an offer has been made stay jumpable.

    - Pre-offer and canceled states are not protected
    - Holds for both enum members and raw values
    """
    assert is_protected_from_queue_jump(state) is False
    assert is_protected_from_queue_jump(state.value) is False


def test_protected_queue_floor_returns_last_protected_position():
    """
    The floor is the highest queue position held by a protected reservation.

    - Protected reservations further back in the queue raise the floor
    - Unprotected reservations do not affect the floor
    """
    reservations = [
        _reservation(1, 100, ApartmentReservationState.SUBMITTED),
        _reservation(2, 200, ApartmentReservationState.OFFER_EXPIRED),
        _reservation(3, 300, ApartmentReservationState.SUBMITTED),
    ]

    assert protected_queue_floor(reservations) == 2


def test_protected_queue_floor_is_zero_without_protected_reservations():
    """
    An untouched queue has no floor.

    - Only unprotected reservations means floor 0
    - Reservations without a queue position are ignored
    """
    reservations = [
        _reservation(1, 100),
        _reservation(None, 200, ApartmentReservationState.CANCELED),
    ]

    assert protected_queue_floor(reservations) == 0


def test_find_haso_insert_target_returns_first_worse_reservation():
    """
    Without protected reservations the newcomer takes the first worse position.

    - Newcomer ranks between the two existing reservations
    - The second reservation's position is returned
    """
    first = _reservation(1, 100)
    second = _reservation(2, 300)

    target = find_haso_insert_target([first, second], 200)

    assert target is second


def test_find_haso_insert_target_skips_protected_queue_head():
    """
    A protected queue head keeps its position.

    - Queue head is OFFER_EXPIRED with a worse ordering number
    - Newcomer is placed at the position behind it
    """
    head = _reservation(1, 500, ApartmentReservationState.OFFER_EXPIRED)
    second = _reservation(2, 800)

    target = find_haso_insert_target([head, second], 100)

    assert target is second


def test_find_haso_insert_target_does_not_pass_protected_reservation_behind_head():
    """
    A protected reservation is not passed even when it is not the queue head.

    - Unprotected reservation at position 1, protected one at position 2
    - Newcomer has the best ordering number
    - No insert target is returned, so the caller appends to the end
    """
    head = _reservation(1, 500)
    protected = _reservation(2, 800, ApartmentReservationState.OFFERED)

    target = find_haso_insert_target([head, protected], 100)

    assert target is None


def test_find_haso_insert_target_respects_ordering_after_protected_reservation():
    """
    Ordering resumes among the unprotected reservations behind the floor.

    - Protected reservation at position 1
    - Two unprotected reservations behind it
    - Newcomer is placed between the unprotected ones
    """
    protected = _reservation(1, 100, ApartmentReservationState.SOLD)
    second = _reservation(2, 300)
    third = _reservation(3, 700)

    target = find_haso_insert_target([protected, second, third], 500)

    assert target is third


def test_find_haso_insert_target_honors_protected_floor_from_other_group():
    """
    A protected reservation outside the scanned group still blocks insertion.

    - Floor of 1 comes from a reservation that is not in the scanned list
    - Scanned reservation at position 1 cannot be passed
    """
    head = _reservation(1, 500)

    target = find_haso_insert_target([head], 100, protected_floor=1)

    assert target is None


def test_find_haso_insert_target_ignores_reservations_without_data():
    """
    Rows lacking a queue position or an ordering number are skipped.

    - Canceled reservation has no queue position
    - Reservation without a right of residence number is not comparable
    """
    canceled = _reservation(None, 100, ApartmentReservationState.CANCELED)
    without_number = _reservation(1, None)
    comparable = _reservation(2, 900)

    target = find_haso_insert_target([canceled, without_number, comparable], 100)

    assert target is comparable


def test_find_haso_insert_target_supports_custom_ordering_number_getter():
    """
    Callers can supply their own ordering number accessor.

    - Ordering number lives on a nested object
    - The getter is used for the comparison
    """
    reservation = SimpleNamespace(
        queue_position=1,
        state=ApartmentReservationState.SUBMITTED,
        application=SimpleNamespace(right_of_residence_ordering_number=800),
    )

    target = find_haso_insert_target(
        [reservation],
        100,
        ordering_number_of=lambda r: r.application.right_of_residence_ordering_number,
    )

    assert target is reservation
