import re
from contextlib import contextmanager
from django.db import transaction
from django.db.transaction import get_connection
from typing import Tuple


# from https://stackoverflow.com/a/54403001
@contextmanager
def lock_table(model):
    with transaction.atomic():
        cursor = get_connection().cursor()
        cursor.execute(f"LOCK TABLE {model._meta.db_table}")
        try:
            yield
        finally:
            cursor.close()


def get_apartment_number_sort_tuple(apartment_number: str) -> Tuple[str, int]:
    """Return a tuple that can be used in sorted() key to sort by apartment number."""
    match = re.match(r"(?P<letters>\D+)?\s*(?P<number>\d+)?", apartment_number)
    return (match.group("letters") or "").strip(), int(match.group("number") or 0)
