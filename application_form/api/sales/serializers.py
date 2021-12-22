import logging
from rest_framework import serializers
from rest_framework.fields import UUIDField

from application_form.api.serializers import ApplicationSerializer
from application_form.services.application import create_application
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
