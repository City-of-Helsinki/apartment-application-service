from typing import Final

# Offset used to temporarily move list_positions out of the way of
# the [1..N] range that the shuffle/reorder will assign. Must be
# larger than any realistic queue size for a single apartment.
LIST_POSITION_BUMP_OFFSET: Final[int] = 10_000
