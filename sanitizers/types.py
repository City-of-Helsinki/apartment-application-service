"""
Generic type-based dump sanitizers for user-input Django fields.

Functions are discovered by database-sanitizer as ``types.<name>`` →
``sanitize_<name>``. Values are returned as strings matching the COPY dump
representation. Counters keep unique / unique-together columns distinct.
"""

from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

_char_counter = itertools.count(1)
_text_counter = itertools.count(1)
_date_counter = itertools.count(0)
_datetime_counter = itertools.count(0)
_integer_counter = itertools.count(1)
_decimal_counter = itertools.count(1)
_float_counter = itertools.count(1)

_EPOCH = date(2000, 1, 1)
_EPOCH_DT = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _passthrough_empty(value: str | None) -> bool:
    """Return True when value should be returned unchanged."""
    return value is None or value == ""


def sanitize_char(value: str | None) -> str | None:
    """Replace a short text / char value with a unique synthetic string."""
    if _passthrough_empty(value):
        return value
    return f"sanitized-char-{next(_char_counter)}"


def sanitize_text(value: str | None) -> str | None:
    """Replace a free-text value with a unique synthetic paragraph."""
    if _passthrough_empty(value):
        return value
    return f"Sanitized text value {next(_text_counter)}."


def sanitize_date(value: str | None) -> str | None:
    """Replace a date with a unique ISO date string."""
    if _passthrough_empty(value):
        return value
    offset = next(_date_counter)
    return (_EPOCH + timedelta(days=offset)).isoformat()


def sanitize_datetime(value: str | None) -> str | None:
    """Replace a datetime with a unique ISO datetime string."""
    if _passthrough_empty(value):
        return value
    offset = next(_datetime_counter)
    return (_EPOCH_DT + timedelta(hours=offset)).isoformat()


def sanitize_integer(value: str | None) -> str | None:
    """Replace an integer with a unique positive integer string."""
    if _passthrough_empty(value):
        return value
    return str(next(_integer_counter))


def sanitize_decimal(value: str | None) -> str | None:
    """Replace a decimal with a unique two-place decimal string."""
    if _passthrough_empty(value):
        return value
    n = next(_decimal_counter)
    return str(Decimal(n) + Decimal("0.01"))


def sanitize_float(value: str | None) -> str | None:
    """Replace a float with a unique float string."""
    if _passthrough_empty(value):
        return value
    n = next(_float_counter)
    return str(float(n) + 0.5)
