from datetime import date, timedelta

import pytest

from invoicing.sap.send.xml_utils import get_posting_date
from invoicing.utils import generate_reference_number


@pytest.mark.parametrize(
    "identifier, expected",
    [
        (118, "28251187"),
        ("123456", "28251234568"),
        (999, "28259998"),
    ],
)
def test_generate_reference_number(identifier, expected):
    assert generate_reference_number(identifier) == expected


class FakeDate(date):
    @classmethod
    def today(cls):
        return date(2025, 9, 1)


@pytest.mark.parametrize(
    "due_date, expected",
    [
        (date(2025, 9, 23), "20250901"),
        (date(2025, 10, 10), "20250910"),
    ],
)
def test_get_posting_date(monkeypatch, due_date, expected):
    monkeypatch.setattr("invoicing.sap.send.xml_utils.date", FakeDate)
    assert get_posting_date(due_date) == expected
