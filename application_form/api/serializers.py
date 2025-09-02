import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone
from enumfields.drf import EnumField, EnumSupportSerializerMixin
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import IntegerField, UUIDField

from apartment.elastic.queries import get_apartment_project_uuid, get_project
from apartment.enums import OwnershipType
from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form import error_codes
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    ApplicationArrivalMethod,
    ApplicationType,
)
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
    Offer,
)
from application_form.services.application import create_application
from application_form.validators import ProjectApplicantValidator, SSNSuffixValidator
from customer.models import Customer

_logger = logging.getLogger(__name__)


User = get_user_model()


class ApplicantSerializerBase(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "street_address",
            "city",
            "postal_code",
            "age",
        ]
        extra_kwargs = {"age": {"read_only": True}}


class ApplicantSerializer(ApplicantSerializerBase):
    date_of_birth = serializers.DateField(write_only=True)

    class Meta(ApplicantSerializerBase.Meta):
        fields = ApplicantSerializerBase.Meta.fields + ["date_of_birth", "ssn_suffix"]

    def validate(self, attrs):
        super().validate(attrs)
        date_of_birth = attrs.get("date_of_birth")
        validator = SSNSuffixValidator(date_of_birth)
        try:
            validator(attrs.get("ssn_suffix", ""))
        except ValidationError as e:
            message = f"Invalid SSN suffix for applicant was received: {e.args[0]}"
            _logger.warning(message)
            raise ValidationError(
                detail={"ssn_suffix": message},
                code=error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID,
            )
        return attrs

    def __init__(self, *args, **kwargs):
        exclude_fields = kwargs.pop("exclude_fields", None)
        super().__init__(*args, **kwargs)
        if exclude_fields:
            for field_name in exclude_fields:
                self.fields.pop(field_name, None)


class ApplicationApartmentSerializer(serializers.Serializer):
    priority = IntegerField(min_value=0, max_value=5)
    identifier = UUIDField()


class ApplicationSerializerBase(serializers.ModelSerializer):
    application_uuid = UUIDField(source="external_uuid")
    application_type = EnumField(ApplicationType, source="type", write_only=True)
    project_id = UUIDField(write_only=True)
    apartments = ApplicationApartmentSerializer(write_only=True, many=True)

    class Meta:
        model = Application
        fields = (
            "application_uuid",
            "application_type",
            "has_children",
            "additional_applicant",
            "right_of_residence",
            "right_of_residence_is_old_batch",
            "project_id",
            "apartments",
            "has_hitas_ownership",
            "is_right_of_occupancy_housing_changer",
        )
        extra_kwargs = {
            # We only support creating applications for now,
            # and only the application UUID will be returned
            # in the response.
            "has_children": {"write_only": True},
            "right_of_residence": {"write_only": True},
            "right_of_residence_is_old_batch": {"write_only": True},
            "project_id": {"write_only": True},
            "has_hitas_ownership": {"write_only": True},
            "is_right_of_occupancy_housing_changer": {"write_only": True},
        }

    def create(self, validated_data):
        # TODO: replace this with SalesApplicationSerializer's POST method code
        validated_data = self.prepare_metadata(validated_data)
        application = create_application(
            validated_data, user=self.context.get("salesperson")
        )
        project = get_project(
            get_apartment_project_uuid(
                validated_data.get("apartments")[0]["identifier"]
            ).project_uuid
        )

        is_late = False

        if project.project_application_end_time:
            is_late = (
                datetime.now().replace(tzinfo=timezone.get_default_timezone())
                > project.project_application_end_time
            )
        is_haso = project.project_ownership_type.lower() == OwnershipType.HASO.value

        if is_late and (not project.project_can_apply_afterwards or not is_haso):
            raise serializers.ValidationError(
                {"detail": "Cannot submit late application to this apartment"},
                code=400,
            )

        if is_late and is_haso and project.project_can_apply_afterwards:
            application.submitted_late = True
            application.save()

        return application

    def prepare_metadata(self, validated_data):
        if validated_data.get("type", None) == ApplicationType.HASO:
            validated_data["process_number"] = METADATA_HASO_PROCESS_NUMBER
        else:
            validated_data["process_number"] = METADATA_HITAS_PROCESS_NUMBER
        validated_data["handler_information"] = METADATA_HANDLER_INFORMATION
        return validated_data


class ApplicationSerializer(ApplicationSerializerBase):
    applicant = ApplicantSerializer(write_only=True)
    additional_applicant = ApplicantSerializer(write_only=True, allow_null=True)
    project_id = UUIDField(write_only=True)

    class Meta(ApplicationSerializerBase.Meta):
        fields = ApplicationSerializerBase.Meta.fields + (
            "applicant",
            "additional_applicant",
        )

    def _get_senders_name_from_applicants_data(self, validated_data):
        additional_applicant = validated_data.get("additional_applicant")
        sender_names = validated_data["profile"].full_name
        if additional_applicant:
            additional_applicant_name = " ".join(
                [additional_applicant["first_name"], additional_applicant["last_name"]]
            )
            sender_names += "/ {}".format(additional_applicant_name)
        return sender_names

    def create(self, validated_data):
        validated_data["profile"] = self.context["request"].user.profile
        return super().create(validated_data)

    def prepare_metadata(self, validated_data):
        validated_data["sender_names"] = self._get_senders_name_from_applicants_data(
            validated_data
        )
        validated_data["method_of_arrival"] = (
            ApplicationArrivalMethod.ELECTRONICAL_SYSTEM
        )
        return super().prepare_metadata(validated_data)

    def validate_ssn_suffix(self, value):
        date_of_birth = self.context["request"].user.profile.date_of_birth
        validator = SSNSuffixValidator(date_of_birth)
        try:
            validator(value)
        except ValidationError as e:
            message = f"""Invalid SSN suffix for the primary applicant was
            received: {e.args[0]}"""
            _logger.warning(message)
            raise ValidationError(
                detail=message,
                code=error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID,
            )
        return value

    def validate(self, attrs):
        project_uuid = attrs["project_id"]
        applicants = []
        applicant_data = attrs.get("applicant")
        if applicant_data:
            applicants.append(
                (applicant_data["date_of_birth"], applicant_data["ssn_suffix"])
            )

        additional_applicant = attrs.get("additional_applicant")
        if additional_applicant:
            applicants.append(
                (
                    additional_applicant["date_of_birth"],
                    additional_applicant["ssn_suffix"],
                )
            )
        validator = ProjectApplicantValidator()
        validator(project_uuid, applicants)

        return super().validate(attrs)


class ReservationOfferSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Offer
        fields = (
            "id",
            "created_at",
            "valid_until",
            "state",
            "concluded_at",
            "comment",
            "is_expired",
        )


class ApartmentReservationSerializerBase(serializers.ModelSerializer):
    state = EnumField(ApartmentReservationState, read_only=True)
    lottery_position = IntegerField(
        source="application_apartment.lotteryeventresult.result_position",
        allow_null=True,
        read_only=True,
    )
    priority_number = serializers.IntegerField(
        source="application_apartment.priority_number", allow_null=True, read_only=True
    )
    offer = ReservationOfferSerializer(read_only=True)

    queue_position_before_cancelation = serializers.IntegerField(
        allow_null=True, required=False, read_only=True, default=None
    )

    class Meta:
        model = ApartmentReservation
        fields = (
            "id",
            "apartment_uuid",
            "lottery_position",
            "queue_position",
            "queue_position_before_cancelation",
            "priority_number",
            "state",
            "offer",
            "right_of_residence",
            "right_of_residence_is_old_batch",
            "has_children",
            "has_hitas_ownership",
            "is_age_over_55",
            "is_right_of_occupancy_housing_changer",
            "submitted_late",
        )
        read_only_fields = (
            "id",
            "lottery_position",
            "queue_position",
            "priority_number",
            "state",
            "right_of_residence",
            "right_of_residence_is_old_batch",
            "has_children",
            "has_hitas_ownership",
            "is_age_over_55",
            "is_right_of_occupancy_housing_changer",
            "submitted_late",
        )

        def to_representation(self, instance):
            data = super().to_representation(instance)
            if instance.queue_position_before_cancelation is None:
                data["queue_position_before_cancelation"] = None
            return data


class ApartmentReservationSerializer(ApartmentReservationSerializerBase):
    pass


class ApartmentReservationStateChangeEventUserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="profile_or_user_first_name")
    last_name = serializers.CharField(source="profile_or_user_last_name")
    email = serializers.EmailField(source="profile_or_user_email")

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email")


class ApartmentReservationStateChangeEventSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    changed_by = ApartmentReservationStateChangeEventUserSerializer(
        source="user", read_only=True
    )
    queue_position = serializers.IntegerField(
        required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = ApartmentReservationStateChangeEvent
        fields = (
            "timestamp",
            "state",
            "comment",
            "cancellation_reason",
            "changed_by",
            "queue_position",
        )
        read_only_fields = (
            "timestamp",
            "changed_by",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].choices.pop(ApartmentReservationState.CANCELED.value)


class ApartmentReservationCancelEventSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    new_customer_id = serializers.PrimaryKeyRelatedField(
        source="replaced_by.customer",
        queryset=Customer.objects.all(),
        required=False,
        help_text="Used only with cancellation reason `transferred`.",
    )
    new_reservation_id = serializers.PrimaryKeyRelatedField(
        source="replaced_by",
        required=False,
        read_only=True,
        help_text="Used only with cancellation reason `transferred`.",
    )

    class Meta:
        model = ApartmentReservationStateChangeEvent
        fields = (
            "timestamp",
            "state",
            "comment",
            "cancellation_reason",
            "new_customer_id",
            "new_reservation_id",
        )
        read_only_fields = ("timestamp", "state", "new_reservation_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cancellation_reason"].required = True
        self.fields["cancellation_reason"].allow_null = False
        self.fields["cancellation_reason"].allow_blank = False

    def validate_cancellation_reason(self, value):
        if value not in (
            ApartmentReservationCancellationReason.TERMINATED,
            ApartmentReservationCancellationReason.CANCELED,
            ApartmentReservationCancellationReason.RESERVATION_AGREEMENT_CANCELED,
            ApartmentReservationCancellationReason.TRANSFERRED,
        ):
            raise ValidationError(f"Illegal value {value}")
        return value

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        if (
            validated_data["cancellation_reason"]
            == ApartmentReservationCancellationReason.TRANSFERRED
        ):
            validated_data["customer"] = validated_data.pop("replaced_by", {}).pop(
                "customer", {}
            )
            if not validated_data["customer"]:
                raise ValidationError(
                    "new_customer_id is required when cancellation_reason is "
                    '"transferred".'
                )
        return validated_data

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if (
            instance.cancellation_reason
            != ApartmentReservationCancellationReason.TRANSFERRED
        ):
            ret.pop("new_customer_id", None)
            ret.pop("new_reservation_id", None)
        return ret


class OfferMessageQueryParamsSerializer(serializers.Serializer):
    valid_until = serializers.DateField(required=False)
