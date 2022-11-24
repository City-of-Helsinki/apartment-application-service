import logging
import math
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from enumfields.drf import EnumSupportSerializerMixin
from rest_framework import serializers
from rest_framework.fields import UUIDField
from uuid import UUID

from apartment.elastic.queries import get_apartment
from apartment.models import ProjectExtraData
from apartment.services import get_offer_message_subject_and_body
from application_form.api.serializers import (
    ApartmentReservationSerializerBase,
    ApplicantSerializerBase,
    ApplicationSerializerBase,
)
from application_form.enums import ApartmentReservationState, ApplicationArrivalMethod
from application_form.models import ApartmentReservation, Applicant, LotteryEvent, Offer
from application_form.services.offer import create_offer, update_offer
from application_form.services.reservation import create_reservation_without_application
from customer.models import Customer
from invoicing.api.serializers import (
    ApartmentInstallmentCandidateSerializer,
    ApartmentInstallmentSerializer,
)
from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
)
from invoicing.models import ProjectInstallmentTemplate
from invoicing.utils import get_euros_from_cents
from users.models import Profile

_logger = logging.getLogger(__name__)


class ProjectUUIDSerializer(serializers.Serializer):
    project_uuid = UUIDField()


class SalesApplicantSerializer(ApplicantSerializerBase):
    pass


class SalesApplicationSerializer(ApplicationSerializerBase):
    profile = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(), write_only=True
    )
    additional_applicant = SalesApplicantSerializer(write_only=True, allow_null=True)

    class Meta(ApplicationSerializerBase.Meta):
        fields = ApplicationSerializerBase.Meta.fields + ("profile",)

    def _get_senders_name_from_applicants_data(self, validated_data):
        additional_applicant = validated_data.get("additional_applicant")
        sender_names = validated_data["profile"].full_name
        if additional_applicant:
            additional_applicant_name = " ".join(
                [additional_applicant["first_name"], additional_applicant["last_name"]]
            )
            sender_names += "/ {}".format(additional_applicant_name)
        return sender_names

    def prepare_metadata(self, validated_data):
        validated_data["sender_names"] = self._get_senders_name_from_applicants_data(
            validated_data
        )
        validated_data["method_of_arrival"] = ApplicationArrivalMethod.POST
        return super().prepare_metadata(validated_data)

    def create(self, validated_data):
        self.context["salesperson"] = self.context["request"].user
        return super().create(validated_data)


class ApplicantCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = ["first_name", "last_name", "is_primary_applicant", "email"]


class ProfileCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = (
            "first_name",
            "last_name",
            "email",
        )


class CustomerCompactSerializer(serializers.ModelSerializer):
    primary_profile = ProfileCompactSerializer()
    secondary_profile = ProfileCompactSerializer()

    class Meta:
        model = Customer
        fields = (
            "id",
            "primary_profile",
            "secondary_profile",
        )


class SalesApartmentReservationSerializer(ApartmentReservationSerializerBase):
    customer = CustomerCompactSerializer()
    cancellation_reason = serializers.SerializerMethodField()
    cancellation_timestamp = serializers.SerializerMethodField()

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = ApartmentReservationSerializerBase.Meta.fields + (
            "customer",
            "cancellation_reason",
            "cancellation_timestamp",
        )
        read_only_fields = fields

    def get_cancellation_reason(self, obj):
        if obj.state == ApartmentReservationState.CANCELED:
            try:
                latest_canceled_event = obj.state_change_events.filter(
                    state=ApartmentReservationState.CANCELED
                ).latest("timestamp")
            except ObjectDoesNotExist:
                return None
            return (
                latest_canceled_event.cancellation_reason.value
                if latest_canceled_event.cancellation_reason
                else None
            )
        return None

    def get_cancellation_timestamp(self, obj):
        if obj.state == ApartmentReservationState.CANCELED:
            try:
                return (
                    obj.state_change_events.filter(
                        state=ApartmentReservationState.CANCELED
                    )
                    .latest("timestamp")
                    .timestamp
                )
            except ObjectDoesNotExist:
                return None
        return None


class SalesWinningApartmentReservationSerializer(SalesApartmentReservationSerializer):
    has_multiple_winning_apartments = serializers.BooleanField(
        source="customer_has_other_winning_apartments"
    )

    class Meta(SalesApartmentReservationSerializer.Meta):
        fields = SalesApartmentReservationSerializer.Meta.fields + (
            "has_multiple_winning_apartments",
        )


class RootApartmentReservationSerializer(ApartmentReservationSerializerBase):
    installments = ApartmentInstallmentSerializer(
        source="apartment_installments", many=True, read_only=True
    )
    installment_candidates = serializers.SerializerMethodField()
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.all()
    )

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = (
            "installments",
            "installment_candidates",
            "customer_id",
        ) + ApartmentReservationSerializerBase.Meta.fields

    @extend_schema_field(ApartmentInstallmentCandidateSerializer(many=True))
    def get_installment_candidates(self, obj):
        apartment_data = get_apartment(obj.apartment_uuid, include_project_fields=True)
        installment_templates = ProjectInstallmentTemplate.objects.filter(
            project_uuid=apartment_data["project_uuid"]
        ).order_by("id")
        apartment_installments = [
            template.get_corresponding_apartment_installment(apartment_data)
            for template in installment_templates
        ]

        flexible_installments = []
        fixed_installments = []
        for installment, template in zip(apartment_installments, installment_templates):
            if (
                template.unit == InstallmentUnit.PERCENT
                and template.percentage_specifier
                == InstallmentPercentageSpecifier.SALES_PRICE_FLEXIBLE
            ):
                flexible_installments.append(installment)
            elif installment.type in [
                InstallmentType.PAYMENT_1,
                InstallmentType.PAYMENT_2,
                InstallmentType.PAYMENT_3,
                InstallmentType.PAYMENT_4,
                InstallmentType.PAYMENT_5,
                InstallmentType.PAYMENT_6,
                InstallmentType.PAYMENT_7,
            ]:
                fixed_installments.append(installment)

        if flexible_installments:
            sales_price = get_euros_from_cents(apartment_data["sales_price"])
            fixed_installments_price = sum(
                installment.value for installment in fixed_installments
            )
            flexible_price = sales_price - fixed_installments_price

            # A bit wonky, but need to be careful not to lose any cents to
            # rounding e.g. if flexible_price was 1.01€ and the number of
            # flexible payments is 3 the quotient is 0.3366 we should get
            # flexible payments of [0.33, 0.33, 0.35]
            if len(flexible_installments) > 1:
                flexible_floor_price = (
                    Decimal(
                        math.floor(flexible_price / len(flexible_installments) * 100)
                    )
                    / 100
                )
                flexible_final_price = (
                    flexible_price
                    - (len(flexible_installments) - 1) * flexible_floor_price
                )
                for flexible_installment in flexible_installments[:-1]:
                    flexible_installment.value = flexible_floor_price
                flexible_installments[-1].value = flexible_final_price
                assert (
                    sum(installment.value for installment in flexible_installments)
                    == flexible_price
                )
            else:
                flexible_installments[0].value = flexible_price

        serializer = ApartmentInstallmentCandidateSerializer(
            apartment_installments,
            many=True,
        )
        return serializer.data

    def validate_apartment_uuid(self, value: UUID) -> UUID:
        try:
            get_apartment(value)
        except ObjectDoesNotExist:
            raise serializers.ValidationError(f"Apartment {value} doesn't exist.")
        if not LotteryEvent.objects.filter(apartment_uuid=value).exists():
            raise serializers.ValidationError(
                f"Cannot create a reservation to apartment {value} because its lottery "
                f"hasn't been executed yet."
            )
        return value

    def create(self, validated_data):
        return create_reservation_without_application(
            validated_data, user=self.context["request"].user
        )


class OfferSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    apartment_reservation_id = serializers.PrimaryKeyRelatedField(
        source="apartment_reservation", queryset=ApartmentReservation.objects.all()
    )

    class Meta:
        model = Offer
        fields = (
            "id",
            "created_at",
            "apartment_reservation_id",
            "valid_until",
            "state",
            "concluded_at",
            "comment",
            "is_expired",
        )
        read_only_fields = ("concluded_at",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context["view"].action in ("update", "partial_update"):
            self.fields["apartment_reservation_id"].read_only = True

    def create(self, validated_data):
        if request := self.context.get("request"):
            user = getattr(request, "user", None)
        else:
            user = None
        return create_offer(validated_data, user=user)

    def update(self, instance, validated_data):
        if request := self.context.get("request"):
            user = getattr(request, "user", None)
        else:
            user = None
        return update_offer(instance, validated_data, user=user)


class ProjectExtraDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectExtraData
        fields = ("offer_message_intro", "offer_message_content")


class RecipientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name")

    class Meta:
        model = Profile
        fields = ("name", "email")


class OfferMessageSerializer(serializers.Serializer):
    subject = serializers.CharField()
    body = serializers.CharField()
    recipients = RecipientSerializer(many=True)

    class Meta:
        fields = ("subject", "body", "recipients")

    def to_representation(self, instance: ApartmentReservation):
        subject, body = get_offer_message_subject_and_body(
            instance, valid_until=self.context.get("valid_until")
        )
        recipients = RecipientSerializer(
            [
                p
                for p in (
                    instance.customer.primary_profile,
                    instance.customer.secondary_profile,
                )
                if p
            ],
            many=True,
        ).data
        return {
            "subject": subject,
            "body": body,
            "recipients": recipients,
        }
