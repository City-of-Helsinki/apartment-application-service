from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from enumfields.drf.fields import EnumField
from enumfields.drf.serializers import EnumSupportSerializerMixin
from rest_framework import exceptions, serializers
from typing import Union

from audit_log import audit_logging
from audit_log.enums import Operation

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import ApartmentInstallment, ProjectInstallmentTemplate
from ..utils import remove_exponent


def is_installment_editable(
    installment: Union[ProjectInstallmentTemplate, ApartmentInstallment]
) -> bool:
    if isinstance(installment, ApartmentInstallment):
        return not bool(
            installment.added_to_be_sent_to_sap_at or installment.sent_to_sap_at
        )
    return True


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


class InstallmentListSerializer(serializers.ListSerializer):
    @transaction.atomic
    def create(self, validated_data):
        now = timezone.now()
        old_installments_by_type = {
            instance.type: instance for instance in self.context["old_instances"]
        }

        new_installments = [
            self.child.create(
                {**new_installment_data, **{"created_at": now, "updated_at": now}}
            )
            if not (
                old_instance := old_installments_by_type.get(
                    new_installment_data["type"]
                )
            )
            else self.child.update(
                old_instance,
                {**new_installment_data, **{"updated_at": now}},
            )
            for new_installment_data in validated_data
        ]

        for old_installment in old_installments_by_type.values():
            if old_installment not in new_installments and is_installment_editable(
                old_installment
            ):
                audit_logging.log(self.get_user(), Operation.DELETE, old_installment)
                old_installment.delete()

        return new_installments

    def get_user(self):
        if request := self.context.get("request"):
            return getattr(request, "user", None)
        return None


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
        list_serializer_class = InstallmentListSerializer

    def create(self, validated_data):
        instance = super().create(validated_data)
        audit_logging.log(self.get_user(), Operation.CREATE, instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        audit_logging.log(self.get_user(), Operation.UPDATE, instance)
        return instance

    def get_user(self):
        if request := self.context.get("request"):
            return getattr(request, "user", None)
        return None


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

    def validate(self, validated_data):
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

        return validated_data

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

    def validate(self, validated_data):
        if (
            validated_data["type"] == InstallmentType.REFUND
            and validated_data["value"] > 0
        ):
            raise exceptions.ValidationError("Refund cannot have a positive value.")
        return validated_data

    def to_internal_value(self, data):
        internal_data = super().to_internal_value(data)
        if user := self.get_user():
            internal_data["handler"] = user.profile_or_user_full_name
        return internal_data

    def update(self, instance, validated_data):
        if not is_installment_editable(instance):
            return instance
        return super().update(instance, validated_data)
