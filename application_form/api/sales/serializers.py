import logging
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import UUIDField

from apartment.elastic.queries import get_apartment
from application_form.api.serializers import (
    ApartmentReservationSerializerBase,
    ApplicantSerializerBase,
    ApplicationSerializerBase,
)
from application_form.models import Applicant
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
    installment_candidates = serializers.SerializerMethodField()

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = (
            "installments",
            "installment_candidates",
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
