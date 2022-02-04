from decimal import Decimal, ROUND_UP


def get_rounded_price(price: Decimal) -> Decimal:
    return price.quantize(Decimal(".01"), rounding=ROUND_UP)


def get_euros_from_cents(in_cents: int) -> Decimal:
    return Decimal(in_cents) / 100
