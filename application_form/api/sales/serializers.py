import logging
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import UUIDField

from application_form import error_codes
from application_form.api.serializers import ApplicationSerializer
from application_form.services.application import create_application
from application_form.validators import SSNSuffixValidator
from users.models import Profile

_logger = logging.getLogger(__name__)


class ProjectUUIDSerializer(serializers.Serializer):
    project_uuid = UUIDField()


class SalesApplicationSerializer(ApplicationSerializer):
    profile = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(), write_only=True
    )

    class Meta(ApplicationSerializer.Meta):
        fields = [
            "application_uuid",
            "application_type",
            "ssn_suffix",
            "has_children",
            "additional_applicant",
            "right_of_residence",
            "project_id",
            "apartments",
            "profile",
        ]

    def create(self, validated_data):
        return create_application(validated_data)

    def validate_ssn_suffix(self, value):
        profile_uuid = self.context["request"].data["profile"]
        applicant_profile = Profile.objects.get(id=profile_uuid)
        date_of_birth = applicant_profile.date_of_birth
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
