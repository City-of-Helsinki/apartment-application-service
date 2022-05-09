from contextlib import contextmanager
from django.db import transaction
from django.db.transaction import get_connection


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
