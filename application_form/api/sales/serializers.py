import logging
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from enumfields.drf import EnumSupportSerializerMixin
from rest_framework import serializers
from rest_framework.fields import UUIDField
from uuid import UUID

from apartment.elastic.queries import get_apartment, get_apartment_uuids
from application_form.api.serializers import (
    ApartmentReservationSerializerBase,
    ApplicantSerializerBase,
    ApplicationSerializerBase,
)
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation, Applicant, LotteryEvent, Offer
from application_form.services.offer import create_offer, update_offer
from application_form.services.reservation import create_reservation
from customer.models import Customer
from invoicing.api.serializers import (
    ApartmentInstallmentCandidateSerializer,
    ApartmentInstallmentSerializer,
)
from invoicing.models import ProjectInstallmentTemplate
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
        fields = ("id", "primary_profile", "secondary_profile")


class SalesApartmentReservationSerializer(ApartmentReservationSerializerBase):
    customer = CustomerCompactSerializer()

    # HITAS fields
    has_children = serializers.SerializerMethodField()

    # HASO fields
    right_of_residence = serializers.CharField(
        source="application_apartment.application.right_of_residence", allow_null=True
    )

    has_multiple_winning_apartments = serializers.SerializerMethodField()

    cancellation_reason = serializers.SerializerMethodField()
    cancellation_timestamp = serializers.SerializerMethodField()

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = ApartmentReservationSerializerBase.Meta.fields + (
            "customer",
            "has_children",
            "right_of_residence",
            "has_multiple_winning_apartments",
            "cancellation_reason",
            "cancellation_timestamp",
        )

    def get_has_multiple_winning_apartments(self, obj):
        """
        Return True if the customer of this reservation already has multiple
        1st place in other apartments of the same project.
        """
        project_uuid = self.context["project_uuid"]
        if not project_uuid:
            return False
        apartment_uuids = get_apartment_uuids(project_uuid)
        # Winning reservation will have state other than SUBMITTED and CANCELED
        return (
            obj.customer.apartment_reservations.reserved()
            .filter(
                apartment_uuid__in=apartment_uuids,
            )
            .count()
            > 1
        )

    def get_has_children(self, obj):
        if obj.application_apartment is not None:
            return obj.application_apartment.application.has_children
        return obj.customer.has_children

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
        serializer = ApartmentInstallmentCandidateSerializer(
            [
                template.get_corresponding_apartment_installment(apartment_data)
                for template in installment_templates
            ],
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
        return create_reservation(validated_data)


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
        )
        read_only_fields = ("concluded_at",)

    def create(self, validated_data):
        return create_offer(validated_data)

    def update(self, instance, validated_data):
        return update_offer(instance, validated_data)
