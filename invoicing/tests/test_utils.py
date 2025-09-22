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


@pytest.mark.parametrize(
    "due_date, today, expected",
    [
        (
            date.today() + timedelta(days=31),
            date.today(),
            (date.today() + timedelta(days=1)).strftime("%Y%m%d"),
        ),
        (
            date.today() + timedelta(days=29),
            date.today(),
            date.today().strftime("%Y%m%d"),
        ),
    ],
)
def test_get_posting_date(monkeypatch, due_date, today, expected):
    monkeypatch.setattr("invoicing.sap.send.xml_utils.date", lambda: today)
    assert get_posting_date(due_date) == expected
