import logging
from enumfields.drf import EnumField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import CharField, IntegerField, UUIDField

from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models import ApartmentReservation, Applicant, Application
from application_form.services.application import create_application
from application_form.validators import ProjectApplicantValidator, SSNSuffixValidator

_logger = logging.getLogger(__name__)


class ApplicantSerializer(serializers.ModelSerializer):
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

    def validate(self, attrs):
        super().validate(attrs)
        date_of_birth = attrs.get("date_of_birth")
        validator = SSNSuffixValidator(date_of_birth)
        try:
            validator(attrs.get("ssn_suffix", ""))
        except ValidationError as e:
            _logger.warning("Invalid SSN suffix for applicant was received: %s", e)
        return attrs


class ApplicationApartmentSerializer(serializers.Serializer):
    priority = IntegerField(min_value=0, max_value=5)
    identifier = UUIDField()


class ApplicationSerializer(serializers.ModelSerializer):
    application_uuid = UUIDField(source="external_uuid")
    application_type = EnumField(ApplicationType, source="type", write_only=True)
    additional_applicant = ApplicantSerializer(write_only=True, allow_null=True)
    project_id = UUIDField(write_only=True)
    ssn_suffix = CharField(write_only=True, min_length=5, max_length=5)
    apartments = ApplicationApartmentSerializer(write_only=True, many=True)

    class Meta:
        model = Application
        fields = [
            "application_uuid",
            "application_type",
            "ssn_suffix",
            "has_children",
            "additional_applicant",
            "right_of_residence",
            "project_id",
            "apartments",
        ]
        extra_kwargs = {
            # We only support creating applications for now,
            # and only the application UUID will be returned
            # in the response.
            "has_children": {"write_only": True},
            "right_of_residence": {"write_only": True},
            "project_id": {"write_only": True},
        }

    def validate_ssn_suffix(self, value):
        date_of_birth = self.context["request"].user.profile.date_of_birth
        validator = SSNSuffixValidator(date_of_birth)
        try:
            validator(value)
        except ValidationError as e:
            _logger.warning(
                "Invalid SSN suffix for the primary applicant was received: %s", e
            )
        return value

    def create(self, validated_data):
        validated_data["profile"] = self.context["request"].user.profile
        return create_application(validated_data)

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


class ApartmentReservationSerializer(serializers.ModelSerializer):
    apartment_uuid = UUIDField(source="apartment.uuid")
    lottery_position = IntegerField(
        source="application_apartment.lotteryeventresult.result_position"
    )
    state = EnumField(ApartmentReservationState)

    class Meta:
        model = ApartmentReservation
        fields = [
            "apartment_uuid",
            "lottery_position",
            "queue_position",
            "state",
        ]
