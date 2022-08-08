from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from enumfields.drf.fields import EnumField
from enumfields.drf.serializers import EnumSupportSerializerMixin
from rest_framework import exceptions, serializers

from audit_log import audit_logging
from audit_log.enums import Operation

from ..enums import InstallmentPercentageSpecifier, InstallmentUnit
from ..models import ApartmentInstallment, ProjectInstallmentTemplate
from ..utils import remove_exponent


class NormalizedDecimalField(serializers.DecimalField):
    """Returns value without trailing zeros."""

    def to_representation(self, value):
        # it would be nicer to set this in __init__(), but that would mess up
        # drf-spectacular's inspection
        self.coerce_to_string = False

        return f"{remove_exponent(super().to_representation(value)):f}"


class IntegerCentsField(serializers.IntegerField):
    """Converts an inner decimal euro value to an int of cents."""

    def to_internal_value(self, value: int) -> Decimal:
        return Decimal(value) / 100

    def to_representation(self, value: Decimal) -> int:
        return int(value * 100)


class InstallmentSerializerBase(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        fields = (
            "type",
            "amount",
            "account_number",
            "due_date",
        )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Project installment template example 1",
            value=[
                {
                    "type": "PAYMENT_1",
                    "percentage": "6.5",
                    "percentage_specifier": "SALES_PRICE",
                    "account_number": "FI49 5000 9420 0287 30",
                    "due_date": "2022-02-18",
                },
                {
                    "type": "REFUND",
                    "amount": 10000,
                    "account_number": "FI49 5000 9420 0287 30",
                    "due_date": None,
                },
            ],
        ),
    ]
)
class ProjectInstallmentTemplateSerializer(InstallmentSerializerBase):
    amount = IntegerCentsField(
        source="get_amount",
        required=False,
        help_text=_("Value in cents. Either this or `percentage` is required."),
    )
    percentage = NormalizedDecimalField(
        max_digits=16,
        decimal_places=2,
        source="get_percentage",
        required=False,
        help_text=_("Either this or `amount` is required."),
    )
    percentage_specifier = EnumField(
        InstallmentPercentageSpecifier,
        help_text=_("This is required with `percentage`."),
        required=False,
    )

    class Meta(InstallmentSerializerBase.Meta):
        model = ProjectInstallmentTemplate
        fields = InstallmentSerializerBase.Meta.fields + (
            "amount",
            "percentage",
            "percentage_specifier",
        )

    def create(self, validated_data):
        if request := self.context.get("request"):
            user = getattr(request, "user", None)
        else:
            user = None
        amount = validated_data.pop("get_amount", None)
        has_amount = amount is not None
        percentage = validated_data.pop("get_percentage", None)
        has_percentage = percentage is not None
        percentage_specifier = validated_data.pop("percentage_specifier", None)

        if (has_amount and has_percentage) or not (has_amount or has_percentage):
            raise exceptions.ValidationError(
                "Either amount or percentage is required but not both."
            )

        if has_amount:
            validated_data.update(
                {
                    "value": amount,
                    "unit": InstallmentUnit.EURO,
                }
            )
        else:
            if not percentage_specifier:
                raise exceptions.ValidationError(
                    "percentage_specifier is required when providing percentage."
                )

            validated_data.update(
                {
                    "value": percentage,
                    "unit": InstallmentUnit.PERCENT,
                    "percentage_specifier": percentage_specifier,
                }
            )

        instance = super().create(validated_data)
        audit_logging.log(user, Operation.CREATE, instance)
        return instance

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


class ApartmentInstallmentSerializerBase(InstallmentSerializerBase):
    amount = IntegerCentsField(
        source="value",
        required=False,
        help_text=_("Value in cents."),
    )

    class Meta(InstallmentSerializerBase.Meta):
        model = ApartmentInstallment


class ApartmentInstallmentCandidateSerializer(ApartmentInstallmentSerializerBase):
    pass


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Apartment installment example 1",
            value=[
                {
                    "type": "PAYMENT_1",
                    "amount": 50000,
                    "account_number": "FI49 5000 9420 0287 30",
                    "due_date": "2022-02-18",
                    "reference_number": "REFERENCE-123",
                },
                {
                    "type": "REFUND",
                    "amount": 10000,
                    "account_number": "FI49 5000 9420 0287 30",
                    "due_date": None,
                    "reference_number": "REFERENCE-321",
                },
            ],
        ),
    ]
)
class ApartmentInstallmentSerializer(ApartmentInstallmentSerializerBase):
    class Meta(ApartmentInstallmentSerializerBase.Meta):
        fields = ApartmentInstallmentSerializerBase.Meta.fields + (
            "reference_number",
            "added_to_be_sent_to_sap_at",
        )
        read_only_fields = ("reference_number", "added_to_be_sent_to_sap_at")

    def create(self, validated_data):
        if request := self.context.get("request"):
            user = getattr(request, "user", None)
        else:
            user = None
        if user:
            validated_data["handler"] = user.full_name
        if old_instance := self.context["old_instances"].get(validated_data["type"]):
            validated_data["reference_number"] = old_instance.reference_number
            validated_data[
                "added_to_be_sent_to_sap_at"
            ] = old_instance.added_to_be_sent_to_sap_at
            validated_data["sent_to_sap_at"] = old_instance.sent_to_sap_at

        instance = super().create(validated_data)
        audit_logging.log(user, Operation.CREATE, instance)
        return instance
