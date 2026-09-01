from typing import Final

from application_form.enums import ApartmentReservationState

# Offset used to temporarily move list_positions out of the way of
# the [1..N] range that the shuffle/reorder will assign. Must be
# larger than any realistic queue size for a single apartment.
LIST_POSITION_BUMP_OFFSET: Final[int] = 10_000

# HASO queue insertion must not place a new application ahead of a reservation
# that has already been offered, even when the new applicant has a better
# (lower) right of residence number. An expired offer stays protected because
# the offer round has already been played out for that queue position.
#
# The states before an offer is made (RESERVED, RESERVATION_AGREEMENT, REVIEW)
# stay jumpable on purpose: they only reflect the current lottery result, which
# right of residence ordering is allowed to change.
PROTECTED_QUEUE_STATES: Final[frozenset] = frozenset(
    {
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_EXPIRED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY,
        ApartmentReservationState.SOLD,
    }
)
PROTECTED_QUEUE_STATE_VALUES: Final[frozenset] = frozenset(
    state.value for state in PROTECTED_QUEUE_STATES
)

# States where the customer is committed to an apartment in the project and must
# not be allowed to apply again. An expired offer is deliberately absent: the
# customer lost that apartment and may apply anew.
COMMITTED_RESERVATION_STATES: Final[frozenset] = frozenset(
    {
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY,
        ApartmentReservationState.SOLD,
    }
)
