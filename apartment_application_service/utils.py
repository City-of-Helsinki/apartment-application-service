import importlib
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
    Helper function for decrypt migrations
    """
    if reverse:
        to_fields = fields
        from_fields = [f"{field}_plain" for field in fields]
    else:
        to_fields = [f"{field}_plain" for field in fields]
        from_fields = fields

    instances = model.objects.all()
    for instance in instances:
        for to_field, from_field in zip(to_fields, from_fields):
            setattr(instance, to_field, getattr(instance, from_field))

        # See comment below
        if reverse:
            instance.save(update_fields=to_fields)

    # Bulk update definitely encrypts data with django-pgcrypto-fields but the
    # encrypted data does no longer decrypt, so there is something fishy!
    if not reverse:
        model.objects.bulk_update(
            instances,
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
            for (app_name, model_name, fields) in ops:
                decrypt_and_update_generic(
                    apps.get_model(app_name, model_name),
                    fields,
                    reverse=reverse,
                )

        return decrypt_and_update_models

    return decrypt_reverse_factory(), decrypt_reverse_factory(True)
