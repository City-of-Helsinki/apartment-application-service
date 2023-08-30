import uuid
from datetime import date, datetime

from django.db import models
from enumfields.drf import EnumSupportSerializerMixin
from rest_framework import serializers

from application_form.models import (
    ApartmentReservation,
    Applicant,
    Application,
    ApplicationApartment,
    LotteryEvent,
    LotteryEventResult,
    Offer,
)
from customer.models import Customer
from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate
from users.models import Profile

from .fields import (
    CustomBooleanField,
    CustomDateField,
    CustomDateTimeField,
    CustomDecimalField,
    CustomPrimaryKeyRelatedField,
)
from .object_store import get_object_store

_object_store = get_object_store()

ADDED_TO_SAP_AT = datetime(2022, 1, 1)
DEFAULT_OFFER_VALID_UNTIL = date(2022, 10, 10)
DEFAULT_SSN_SUFFIX = "XXXXX"
DEFAULT_AGE = 1000
DEFAULT_DATE_OR_BIRTH = date(1900, 1, 1)

PROJECT_UUID_NAMESPACE = uuid.UUID("11111111-1111-1111-1111-111111111111")
APARTMENT_UUID_NAMESPACE = uuid.UUID("22222222-2222-2222-2222-222222222222")


def get_project_uuid(asko_id):
    return uuid.uuid5(PROJECT_UUID_NAMESPACE, asko_id)


def get_apartment_uuid(asko_id):
    return uuid.uuid5(APARTMENT_UUID_NAMESPACE, asko_id)


class CustomModelSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serializer_field_mapping[models.BooleanField] = CustomBooleanField
        self.serializer_field_mapping[models.DateField] = CustomDateField
        self.serializer_field_mapping[models.DateTimeField] = CustomDateTimeField
        self.serializer_field_mapping[models.DecimalField] = CustomDecimalField
        self.serializer_related_field = CustomPrimaryKeyRelatedField


class ProfileSerializer(CustomModelSerializer):
    email = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    date_of_birth = CustomDateField(required=False)

    class Meta:
        model = Profile
        fields = "__all__"

    def to_internal_value(self, data):
        data["contact_language"] = "fi"
        return super().to_internal_value(data)


class CustomerSerializer(CustomModelSerializer):
    last_contact_date = CustomDateField(required=False)

    class Meta:
        model = Customer
        exclude = ("id",)


class ApplicantSerializer(CustomModelSerializer):
    application = CustomPrimaryKeyRelatedField(queryset=Application.objects.all())
    email = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    date_of_birth = CustomDateField(required=False, default=DEFAULT_DATE_OR_BIRTH)
    age = serializers.IntegerField(required=False, default=DEFAULT_AGE)
    ssn_suffix = serializers.CharField(required=False, default=DEFAULT_SSN_SUFFIX)

    class Meta:
        model = Applicant
        fields = (
            "application",
            "age",
            "city",
            "date_of_birth",
            "email",
            "first_name",
            "last_name",
            "is_primary_applicant",
            "phone_number",
            "postal_code",
            "ssn_suffix",
            "street_address",
        )


class ApplicationSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    customer = CustomPrimaryKeyRelatedField(queryset=Customer.objects.all())
    has_children = CustomBooleanField()
    has_hitas_ownership = CustomBooleanField()
    is_right_of_occupancy_housing_changer = CustomBooleanField()
    submitted_late = CustomBooleanField()

    class Meta:
        model = Application
        fields = (
            "id",
            "customer",
            "has_children",
            "has_hitas_ownership",
            "is_right_of_occupancy_housing_changer",
            "right_of_residence",
            "submitted_late",
            "type",
            "applicants_count",
        )

    def to_internal_value(self, data):
        # will be populated later
        data["applicants_count"] = 0
        return super().to_internal_value(data)


class ApartmentReservationSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    application_apartment = CustomPrimaryKeyRelatedField(
        queryset=ApplicationApartment.objects.all()
    )

    class Meta:
        model = ApartmentReservation
        fields = (
            "state",
            "apartment_uuid",
            "customer",
            "list_position",
            "application_apartment",
            "right_of_residence",
        )

    def to_internal_value(self, data):
        data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])

        data["state"] = data.pop("state").lower().replace(" ", "_")
        data["customer"] = _object_store.get(Customer, data["customer"]).pk

        # will be populated later
        data["list_position"] = 0

        data = super().to_internal_value(data)

        data["right_of_residence"] = data[
            "application_apartment"
        ].application.right_of_residence
        return data


class ApplicationApartmentSerializer(serializers.ModelSerializer):
    application = CustomPrimaryKeyRelatedField(queryset=Application.objects.all())

    class Meta:
        model = ApplicationApartment
        fields = ("application", "apartment_uuid", "priority_number")

    def to_internal_value(self, data):
        data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])
        return super().to_internal_value(data)


class ProjectInstallmentTemplateSerializer(CustomModelSerializer):
    due_date = CustomDateField(required=False)

    class Meta:
        model = ProjectInstallmentTemplate
        fields = "__all__"

    def to_internal_value(self, data):
        data["project_uuid"] = get_project_uuid(data["project_uuid"])

        if not data.get("percentage_specifier"):
            data["percentage_specifier"] = "SALES_PRICE"

        return super().to_internal_value(data)


class ApartmentInstallmentSerializer(CustomModelSerializer):
    due_date = serializers.DateField(
        required=False, input_formats=["%d.%m.%Y %H:%M:%S"]
    )

    class Meta:
        model = ApartmentInstallment
        fields = "__all__"

    def to_internal_value(self, data):
        data["added_to_be_sent_to_sap_at"] = ADDED_TO_SAP_AT
        data["sent_to_sap_at"] = ADDED_TO_SAP_AT
        return super().to_internal_value(data)


class LotteryEventSerializer(CustomModelSerializer):
    class Meta:
        model = LotteryEvent
        fields = ("apartment_uuid", "timestamp")

    def to_internal_value(self, data):
        data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])
        return super().to_internal_value(data)


class LotteryEventResultSerializer(CustomModelSerializer):
    class Meta:
        model = LotteryEventResult
        fields = ("event", "application_apartment", "result_position")


class OfferSerializer(CustomModelSerializer):
    valid_until = CustomDateField(required=False, default=DEFAULT_OFFER_VALID_UNTIL)
    concluded_at = CustomDateTimeField(required=False)

    class Meta:
        model = Offer
        fields = (
            "apartment_reservation",
            "valid_until",
            "state",
            "concluded_at",
            "comment",
        )

    def to_internal_value(self, data):
        if "state" in data:
            data["state"] = data["state"].lower()
        return super().to_internal_value(data)
