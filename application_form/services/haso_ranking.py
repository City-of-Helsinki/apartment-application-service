from typing import Any, Callable, Iterable, Optional

from application_form.services.constants import PROTECTED_QUEUE_STATE_VALUES


def _reservation_state(reservation_or_state: Any) -> Any:
    """
    Resolve a reservation state from a reservation or a raw state value.

    Parameters:
        reservation_or_state: Reservation-like object with a ``state`` attribute,
            or a raw reservation state enum/value.

    Returns:
        Any: Reservation state enum member or database value.
    """
    if hasattr(reservation_or_state, "state"):
        return reservation_or_state.state
    return reservation_or_state


def _has_expired_offer(reservation_or_state: Any) -> bool:
    """
    Tell whether a reservation has a date-expired offer.

    Parameters:
        reservation_or_state: Reservation-like object, or a raw state value.

    Returns:
        bool: True when an attached offer reports ``is_expired``.
    """
    if not hasattr(reservation_or_state, "offer"):
        return False
    offer = reservation_or_state.offer
    return bool(getattr(offer, "is_expired", False))


def is_protected_from_queue_jump(reservation_or_state: Any) -> bool:
    """
    Tell whether a reservation may not be passed in a HASO queue.

    Accepts either a reservation (or stand-in with ``state`` / ``offer``) or a
    raw reservation state enum/value. A date-expired offer protects the
    reservation even when its state is still jumpable (for example SUBMITTED).

    Parameters:
        reservation_or_state: Reservation-like object, or a reservation state
            enum member / database value.

    Returns:
        bool: True when a new application must not be placed ahead of the
            reservation.
    """
    if _has_expired_offer(reservation_or_state):
        return True
    state = _reservation_state(reservation_or_state)
    return getattr(state, "value", state) in PROTECTED_QUEUE_STATE_VALUES


def protected_queue_floor(reservations: Iterable) -> int:
    """
    Find the last queue position that a new application must not pass.

    Parameters:
        reservations (Iterable): Active reservations of a single apartment.

    Returns:
        int: Highest queue position held by a protected reservation, or 0 when
            the queue holds none.
    """
    return max(
        (
            reservation.queue_position
            for reservation in reservations
            if reservation.queue_position is not None
            and is_protected_from_queue_jump(reservation)
        ),
        default=0,
    )


def _right_of_residence_ordering_number(reservation: Any) -> Optional[int]:
    return reservation.right_of_residence_ordering_number


def find_haso_insert_target(
    ordered_reservations: Iterable,
    ordering_number: Optional[int],
    *,
    ordering_number_of: Callable[[Any], Optional[int]] = (
        _right_of_residence_ordering_number
    ),
    protected_floor: int = 0,
) -> Optional[Any]:
    """
    Find the reservation whose queue position a new HASO application takes.

    The new application is ranked by right of residence number among the given
    reservations, but it may never be placed ahead of a protected reservation.
    Every protected reservation therefore invalidates the positions found
    before it, which keeps the search behind the last protected reservation.

    Parameters:
        ordered_reservations (Iterable): Reservations competing with the new
            application, ordered by ascending queue position.
        ordering_number (Optional[int]): Right of residence ordering number of
            the new application.
        ordering_number_of (Callable): Reads the ordering number of a
            reservation in ``ordered_reservations``.
        protected_floor (int): Queue position of the last protected reservation
            outside ``ordered_reservations``, as returned by
            ``protected_queue_floor``.

    Returns:
        Optional[Any]: Reservation to insert in front of, or None when the new
            application belongs at the end of the queue.
    """
    if ordering_number is None:
        return None

    target = None
    for reservation in ordered_reservations:
        queue_position = reservation.queue_position
        if queue_position is None:
            continue
        if (
            is_protected_from_queue_jump(reservation)
            or queue_position <= protected_floor
        ):
            target = None
            continue
        if target is not None:
            continue
        other_ordering_number = ordering_number_of(reservation)
        if (
            other_ordering_number is not None
            and ordering_number < other_ordering_number
        ):
            target = reservation
    return target
