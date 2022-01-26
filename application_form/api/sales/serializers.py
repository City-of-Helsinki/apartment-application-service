import logging
from rest_framework import serializers
from rest_framework.fields import UUIDField

from application_form.api.serializers import (
    ApplicantSerializerBase,
    ApplicationSerializerBase,
)
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
