import re
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from .logger import LOG

NIN_RX = re.compile(
    r"(0[1-9]|[1-2]\d|3[01])(0[1-9]|1[0-2])\d\d ?[-A]{0,2} ?\d\d\d[0-9A-Z]",
    re.IGNORECASE,
)
NIN_FIELD_NAMES = ["ssn", "nin", "hetu", "sotu"]

# Value to use when redacting NINs
REDACTED_NIN = "<NIN?>"

# Scalar types, which don't need to be redacted
NON_NIN_SCALAR_TYPES = (bool, int, float, complex, UUID, Decimal, date)


def redact_nin_values(data: Any) -> Any:
    if isinstance(data, str):
        return NIN_RX.sub(REDACTED_NIN, data)
    elif isinstance(data, (list, tuple, set, frozenset)):
        return type(data)(redact_nin_values(x) for x in data)
    elif isinstance(data, bytes):
        return redact_nin_values(data.decode("utf-8", errors="replace"))
    elif isinstance(data, dict):
        return {
            k: REDACTED_NIN if is_nin_field_name(k) else redact_nin_values(v)
            for (k, v) in data.items()
        }
    elif data is None or isinstance(data, NON_NIN_SCALAR_TYPES):
        return data
    LOG.error("Don't know how to redact NIN values in type %s", type(data))
    return f"<REDACTED DATA OF TYPE {type(data).__name__}>"


def is_nin_field_name(field_name: str) -> bool:
    return any(x in field_name.lower() for x in NIN_FIELD_NAMES)
