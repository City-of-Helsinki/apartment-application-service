import logging
from rest_framework import serializers
from rest_framework.fields import UUIDField

from application_form.api.serializers import (
    ApartmentReservationSerializerBase,
    ApplicantSerializerBase,
    ApplicationSerializerBase,
)
from application_form.models import Applicant
from invoicing.api.serializers import ApartmentInstallmentSerializer
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
    ssn = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = ["first_name", "last_name", "is_primary_applicant", "ssn"]

    def get_ssn(self, obj):
        return obj.date_of_birth.strftime("%y%m%d") + obj.ssn_suffix


class ApartmentReservationSerializer(ApartmentReservationSerializerBase):
    applicants = ApplicantCompactSerializer(
        source="application_apartment.application.applicants", many=True
    )

    # HITAS fields
    has_children = serializers.BooleanField(
        source="application_apartment.application.has_children"
    )

    # HASO fields
    right_of_residence = serializers.CharField(
        source="application_apartment.application.right_of_residence"
    )

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = ApartmentReservationSerializerBase.Meta.fields + (
            "applicants",
            "has_children",
            "right_of_residence",
        )


class RootApartmentReservationSerializer(ApartmentReservationSerializerBase):
    installments = ApartmentInstallmentSerializer(
        source="apartment_installments", many=True
    )

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = ("installments",) + ApartmentReservationSerializerBase.Meta.fields
