import logging
from enumfields.drf import EnumField, EnumSupportSerializerMixin
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import CharField, IntegerField, UUIDField

from application_form import error_codes
from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
)
from application_form.services.application import create_application
from application_form.validators import ProjectApplicantValidator, SSNSuffixValidator

_logger = logging.getLogger(__name__)


class ApplicantSerializerBase(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(write_only=True)

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
            "date_of_birth",
            "ssn_suffix",
        ]
        extra_kwargs = {"age": {"read_only": True}}


class ApplicantSerializer(ApplicantSerializerBase):
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


class ApplicationApartmentSerializer(serializers.Serializer):
    priority = IntegerField(min_value=0, max_value=5)
    identifier = UUIDField()


class ApplicationSerializerBase(serializers.ModelSerializer):
    application_uuid = UUIDField(source="external_uuid")
    application_type = EnumField(ApplicationType, source="type", write_only=True)
    project_id = UUIDField(write_only=True)
    ssn_suffix = CharField(write_only=True, min_length=5, max_length=5)
    apartments = ApplicationApartmentSerializer(write_only=True, many=True)

    class Meta:
        model = Application
        fields = (
            "application_uuid",
            "application_type",
            "ssn_suffix",
            "has_children",
            "additional_applicant",
            "right_of_residence",
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
            "project_id": {"write_only": True},
            "has_hitas_ownership": {"write_only": True},
            "is_right_of_occupancy_housing_changer": {"write_only": True},
        }

    def create(self, validated_data):
        return create_application(validated_data)


class ApplicationSerializer(ApplicationSerializerBase):
    additional_applicant = ApplicantSerializer(write_only=True, allow_null=True)
    project_id = UUIDField(write_only=True)

    def create(self, validated_data):
        validated_data["profile"] = self.context["request"].user.profile
        return super().create(validated_data)

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
        profile = self.context["request"].user.profile
        applicants.append((profile.date_of_birth, attrs["ssn_suffix"]))
        is_additional_applicant = (
            "additional_applicant" in attrs
            and attrs["additional_applicant"] is not None
        )
        if is_additional_applicant:
            applicants.append(
                (
                    attrs["additional_applicant"]["date_of_birth"],
                    attrs["additional_applicant"]["ssn_suffix"],
                )
            )
        validator = ProjectApplicantValidator()
        validator(project_uuid, applicants)

        return super().validate(attrs)


class ApartmentReservationSerializerBase(serializers.ModelSerializer):
    state = EnumField(ApartmentReservationState)

    class Meta:
        model = ApartmentReservation
        fields = (
            "id",
            "apartment_uuid",
            "list_position",
            "queue_position",
            "state",
        )


class ApartmentReservationSerializer(ApartmentReservationSerializerBase):
    pass


class ApartmentReservationStateChangeEventSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = ApartmentReservationStateChangeEvent
        fields = ("timestamp", "state", "comment")
        read_only_fields = ("timestamp",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].choices.pop(ApartmentReservationState.CANCELED.value)


class ApartmentReservationCancelEventSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = ApartmentReservationStateChangeEvent
        fields = ("timestamp", "state", "comment", "cancellation_reason")
        read_only_fields = ("timestamp", "state")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cancellation_reason"].required = True
        self.fields["cancellation_reason"].allow_null = False
        self.fields["cancellation_reason"].allow_blank = False
