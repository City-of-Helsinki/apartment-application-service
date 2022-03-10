from decimal import Decimal, ROUND_UP
from itertools import cycle
from typing import Union

REFERENCE_NUMBER_PREFIX = "2825"


def get_rounded_price(price: Decimal) -> Decimal:
    return price.quantize(Decimal(".01"), rounding=ROUND_UP)


def get_euros_from_cents(in_cents: int) -> Decimal:
    return Decimal(in_cents) / 100


def generate_reference_number(identifier: Union[int, str]) -> str:
    actual = f"{REFERENCE_NUMBER_PREFIX}{identifier}"

    coefficients = (7, 3, 1)
    check_digit = (
        10 - sum(int(d) * c for d, c in zip(reversed(actual), cycle(coefficients))) % 10
    )

    return f"{actual}{check_digit}"
