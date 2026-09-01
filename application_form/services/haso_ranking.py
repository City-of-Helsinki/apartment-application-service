from typing import Any, Callable, Iterable, Optional

from application_form.services.constants import PROTECTED_QUEUE_STATE_VALUES


def is_protected_from_queue_jump(state: Any) -> bool:
    """
    Tell whether a reservation may not be passed in a HASO queue.

    Parameters:
        state: Reservation state, either an enum member or its database value.

    Returns:
        bool: True when a new application must not be placed ahead of the
            reservation.
    """
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
            and is_protected_from_queue_jump(reservation.state)
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
            is_protected_from_queue_jump(reservation.state)
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
