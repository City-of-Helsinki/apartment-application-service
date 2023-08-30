from rest_framework import serializers

from .log_utils import log_debug_data
from .logger import LOG
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
            _object_store.get_id(self.queryset.model, data)
        )


class TruncatingCharField(serializers.CharField):
    def __init__(self, *, max_length: int, **kwargs):
        assert isinstance(max_length, int) and max_length > 0
        super().__init__(max_length=max_length, **kwargs)
        self.max_length = max_length

    def to_internal_value(self, data):
        if isinstance(data, str) and len(data) > self.max_length:
            LOG.warning(
                "Truncating %d characters to %d characters in field %s",
                len(data),
                self.max_length,
                self.field_name,
            )
            truncated = data[: self.max_length]
            log_debug_data("Truncation: %s -> %s", data, truncated)
            data = truncated
        return super().to_internal_value(data)
