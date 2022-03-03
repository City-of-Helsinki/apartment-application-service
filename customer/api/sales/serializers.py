from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from uuid import UUID

from apartment.elastic.queries import get_apartment
from application_form.api.serializers import ApartmentReservationSerializerBase
from application_form.models import ApartmentReservation
from customer.models import Customer
from invoicing.api.serializers import ApartmentInstallmentSerializer
from users.api.sales.serializers import ProfileSerializer
from users.models import Profile


class CustomerApartmentReservationSerializer(ApartmentReservationSerializerBase):
    project_uuid = serializers.SerializerMethodField()
    project_housing_company = serializers.SerializerMethodField()
    project_ownership_type = serializers.SerializerMethodField()
    project_street_address = serializers.SerializerMethodField()
    project_district = serializers.SerializerMethodField()
    apartment_number = serializers.SerializerMethodField()
    apartment_structure = serializers.SerializerMethodField()
    apartment_living_area = serializers.SerializerMethodField()
    apartment_sales_price = serializers.SerializerMethodField()
    apartment_debt_free_sales_price = serializers.SerializerMethodField()
    apartment_right_of_occupancy_payment = serializers.SerializerMethodField()
    apartment_installments = ApartmentInstallmentSerializer(many=True)

    class Meta(ApartmentReservationSerializerBase.Meta):
        model = ApartmentReservation
        fields = (
            "id",
            "project_uuid",
            "project_housing_company",
            "project_ownership_type",
            "project_street_address",
            "project_district",
            "apartment_uuid",
            "apartment_number",
            "apartment_structure",
            "apartment_living_area",
            "apartment_sales_price",
            "apartment_debt_free_sales_price",
            "apartment_right_of_occupancy_payment",
            "apartment_installments",
        ) + ApartmentReservationSerializerBase.Meta.fields

    def to_representation(self, instance):
        self.context["apartment"] = get_apartment(
            instance.apartment_uuid, include_project_fields=True
        )
        return super().to_representation(instance)

    def get_project_uuid(self, obj) -> UUID:
        return self.context["apartment"].project_uuid

    def get_project_housing_company(self, obj) -> str:
        return self.context["apartment"].project_housing_company

    def get_project_ownership_type(self, obj) -> str:
        return self.context["apartment"].project_ownership_type

    def get_project_street_address(self, obj) -> str:
        return self.context["apartment"].project_street_address

    def get_project_district(self, obj) -> str:
        return self.context["apartment"].project_district

    def get_apartment_number(self, obj) -> str:
        return self.context["apartment"].apartment_number

    def get_apartment_structure(self, obj) -> str:
        return self.context["apartment"].apartment_structure

    def get_apartment_living_area(self, obj) -> float:
        return self.context["apartment"].living_area

    def get_apartment_sales_price(self, obj) -> int:
        return self.context["apartment"].sales_price

    def get_apartment_debt_free_sales_price(self, obj) -> int:
        return self.context["apartment"].debt_free_sales_price

    def get_apartment_right_of_occupancy_payment(self, obj) -> int:
        return self.context["apartment"].right_of_occupancy_payment


class CustomerSerializer(serializers.ModelSerializer):
    primary_profile = ProfileSerializer()
    secondary_profile = ProfileSerializer(required=False, allow_null=True)
    apartment_reservations = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = (
            "id",
            "additional_information",
            "created_at",
            "has_children",
            "has_hitas_ownership",
            "is_age_over_55",
            "is_right_of_occupancy_housing_changer",
            "last_contact_date",
            "primary_profile",
            "right_of_residence",
            "secondary_profile",
            "apartment_reservations",
        )

    @extend_schema_field(CustomerApartmentReservationSerializer(many=True))
    def get_apartment_reservations(self, obj):
        reservations = ApartmentReservation.objects.filter(
            application_apartment__application__customer=obj
        )
        return CustomerApartmentReservationSerializer(reservations, many=True).data

    @transaction.atomic
    def create(self, validated_data):
        primary_profile_data = validated_data.pop("primary_profile")
        primary_profile = Profile.objects.create(**primary_profile_data)
        if secondary_profile_data := validated_data.pop("secondary_profile", None):
            secondary_profile = Profile.objects.create(**secondary_profile_data)
        else:
            secondary_profile = None

        customer = Customer.objects.create(
            primary_profile=primary_profile,
            secondary_profile=secondary_profile,
            **validated_data,
        )

        return customer


class CustomerListSerializer(serializers.ModelSerializer):
    primary_first_name = serializers.CharField(source="primary_profile.first_name")
    primary_last_name = serializers.CharField(source="primary_profile.last_name")
    primary_email = serializers.CharField(source="primary_profile.email")
    primary_phone_number = serializers.CharField(source="primary_profile.phone_number")

    secondary_first_name = serializers.SerializerMethodField()
    secondary_last_name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "primary_first_name",
            "primary_last_name",
            "primary_email",
            "primary_phone_number",
            "secondary_first_name",
            "secondary_last_name",
        ]

    def get_secondary_first_name(self, obj):
        if obj.secondary_profile:
            return obj.secondary_profile.first_name
        return None

    def get_secondary_last_name(self, obj):
        if obj.secondary_profile:
            return obj.secondary_profile.last_name
        return None
