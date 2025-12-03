import importlib
import re
from typing import Callable, Iterable, Tuple

from django.db.models import Model


class SafeAttributeObject:
    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, item):
        try:
            return getattr(self.obj, item)
        except AttributeError:
            return None


def update_obj(obj, data):
    for field, value in data.items():
        setattr(obj, field, value)
    obj.save()
    return obj


def is_module_available(module_name):
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True


def decrypt_and_update_generic(model: Model, fields, reverse=False):
    """
    Helper function for decrypt migrations. Iterates through the model rows
    and copies data on each instance. Uses iterator + bulk update in forward (decrypt)
    migration, but a slow iterator + save in reverse (encrypt) migration. pgcrypto
    seems to corrupt data with bulk update.
    """
    if reverse:
        to_fields = fields
        from_fields = [f"{field}_plain" for field in fields]
    else:
        to_fields = [f"{field}_plain" for field in fields]
        from_fields = fields

    instances_qs = model.objects.all().only(*from_fields)
    instances_to_update = []
    chunk_size = 2000
    for instance in instances_qs.iterator(chunk_size=chunk_size):
        for to_field, from_field in zip(to_fields, from_fields):
            setattr(instance, to_field, getattr(instance, from_field))

        # See comment below
        if reverse:
            instance.save(update_fields=to_fields)
        else:
            instances_to_update.append(instance)
            if len(instances_to_update) == chunk_size:
                model.objects.bulk_update(
                    instances_to_update,
                    to_fields,
                )
                instances_to_update = []

    # Bulk update definitely encrypts data with django-pgcrypto-fields but the
    # encrypted data does no longer decrypt, so there is something fishy!
    if not reverse and instances_to_update:
        model.objects.bulk_update(
            instances_to_update,
            to_fields,
        )


def decrypt_factory(
    ops: Iterable[Tuple[str, str, Iterable[str]]]
) -> Tuple[Callable, Callable]:
    """
    Utility function for generating the forward and reverse functions for
    migrating data out of PGP encrypted fields.
    """

    def decrypt_reverse_factory(reverse=False) -> Callable:
        def decrypt_and_update_models(apps, schema_editor):
            for app_name, model_name, fields in ops:
                decrypt_and_update_generic(
                    apps.get_model(app_name, model_name),
                    fields,
                    reverse=reverse,
                )

        return decrypt_and_update_models

    return decrypt_reverse_factory(), decrypt_reverse_factory(True)


# regex to detect sensitive data such as national identification number
SENTRY_SENSITIVE_PATTERNS = [
    # Finnish National Identification Number: DDMMYY[+-ABCDEFYXWVU]ZZZC
    # (?!-) = negative lookahead to prevent capturing 
    # parts of uuids such as "-910T" in b1377ac0-ad05-4f21-910T-13ee78b4740d
    (
        re.compile(r"(?:\b\d{6})?[-+ABCDEFYXWVU]\d{3}[0-9A-Z]\b(?!-)", re.IGNORECASE),
        "[FILTERED_NATIONAL_IDENTIFICATION_NUMBER]",
    ),  # noqa: E501
]


def scrub_sensitive_payload(event, hint):
    """Sentry before_send hook to recursively scrub sensitive data from event payloads.

    Args:
        event (dict): The Sentry event dictionary containing exception info,
            stacktrace, contexts, etc.
        hint (dict): A dictionary containing origin data
            (e.g., the original exception object).

    Returns:
        dict: The modified event dictionary with sensitive patterns redacted.
    """

    def recursive_scrub(item):
        """Helper to traverse dicts, lists, and strings."""

        # If it's a string, apply ALL patterns in sequence
        if isinstance(item, str):
            scrubbed_item = item
            for pattern, replacement in SENTRY_SENSITIVE_PATTERNS:
                # If the pattern is found, substitute it
                if pattern.search(scrubbed_item):
                    scrubbed_item = pattern.sub(replacement, scrubbed_item)
            return scrubbed_item

        # If it's a dictionary, recurse into values (preserve keys)
        if isinstance(item, dict):
            return {key: recursive_scrub(value) for key, value in item.items()}

        # If it's a list/tuple, recurse into elements
        if isinstance(item, (list, tuple)):
            return [recursive_scrub(element) for element in item]

        # Return primitives (int, float, None, bool) as-is
        return item

    # Apply the recursive scrubbing to the entire event dictionary
    return recursive_scrub(event)
