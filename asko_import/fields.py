from rest_framework import serializers

from .object_store import get_object_store

_object_store = get_object_store()


class CustomBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if data == "0":
            return False
        elif data == "-1":
            return True
        return super().to_internal_value(data)


class CustomDateField(serializers.DateField):
    def __init__(self, *args, **kwargs):
        kwargs["input_formats"] = ["%d.%m.%Y", "%d.%m.%Y %H:%M:%S"]
        super().__init__(*args, **kwargs)


class CustomDateTimeField(serializers.DateTimeField):
    def __init__(self, *args, **kwargs):
        kwargs["input_formats"] = ["%d.%m.%Y %H:%M:%S"]
        super().__init__(*args, **kwargs)


class CustomDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        if type(data) is str:
            data = data.replace(" ", "").replace(",", ".").replace("€", "")
        return super().to_internal_value(data)


class CustomPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        return super().to_internal_value(
            _object_store.get(self.queryset.model, data).pk
        )
