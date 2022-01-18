from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from enumfields.drf.serializers import EnumSupportSerializerMixin
from rest_framework import serializers

from .enums import InstallmentUnit
from .models import ProjectInstallmentTemplate


class NormalizedDecimalField(serializers.DecimalField):
    """Returns value without trailing zeros."""

    def to_representation(self, value):
        # it would be nicer to set this in __init__(), but that would mess up
        # drf-spectacular's inspection
        self.coerce_to_string = False

        return f"{self.remove_exponent(super().to_representation(value)):f}"

    # from https://docs.python.org/3/library/decimal.html#decimal-faq
    @staticmethod
    def remove_exponent(d: Decimal) -> Decimal:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


class IntegerCentsField(serializers.IntegerField):
    """Converts an inner decimal euro value to an int of cents."""

    def to_internal_value(self, value: int) -> Decimal:
        return Decimal(value) / 100

    def to_representation(self, value: Decimal) -> int:
        return int(value * 100)


class ProjectInstallmentTemplateSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    amount = IntegerCentsField(
        source="get_amount", required=False, help_text=_("In cents.")
    )
    percentage = NormalizedDecimalField(
        max_digits=16, decimal_places=2, source="get_percentage", required=False
    )

    class Meta:
        model = ProjectInstallmentTemplate
        fields = (
            "type",
            "amount",
            "percentage",
            "percentage_specifier",
            "account_number",
            "due_date",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if instance.unit == InstallmentUnit.EURO:
            data.pop("percentage")
            data.pop("percentage_specifier")
        elif instance.unit == InstallmentUnit.PERCENT:
            data.pop("amount")
        else:
            raise ValueError(
                f'"{instance}" has invalid installment unit "{instance.unit}".'
            )

        return data
