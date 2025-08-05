from decimal import Decimal
from connections.utils import convert_price_from_cents_to_eur


class TestCommonConnectionUtils:
    def test_convert_price_from_cents_to_eur(self):
        assert convert_price_from_cents_to_eur(10000) == Decimal("100.0")
        assert convert_price_from_cents_to_eur(12345.67) == Decimal("123.46")

