from uuid import UUID

from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apartment.elastic.queries import get_apartment
from apartment_application_service.utils import update_obj
from application_form.api.serializers import (
    ApartmentReservationSerializerBase,
    ApartmentReservationStateChangeEventSerializer,
)
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation, LotteryEvent
from application_form.utils import get_apartment_number_sort_tuple
from customer.models import Customer, CustomerComment
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
    state_change_events = ApartmentReservationStateChangeEventSerializer(many=True)
    project_lottery_completed = serializers.SerializerMethodField()

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
            "state_change_events",
            "project_lottery_completed",
        ) + ApartmentReservationSerializerBase.Meta.fields

    def to_representation(self, instance):
        self.context["apartment"] = get_apartment(
            instance.apartment_uuid, include_project_fields=True
        )
        self.context["reservation_id"] = instance.id
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
        return self.context["apartment"].reservation_right_of_occupancy_payment(
            self.context["reservation_id"]
        )

    def get_project_lottery_completed(self, obj) -> bool:
        lottery_completed = LotteryEvent.objects.filter(
            apartment_uuid=obj.apartment_uuid
        ).exists()
        return lottery_completed


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
            "right_of_residence_is_old_batch",
            "secondary_profile",
            "apartment_reservations",
        )

    @extend_schema_field(CustomerApartmentReservationSerializer(many=True))
    def get_apartment_reservations(self, obj):
        reservations = ApartmentReservation.objects.filter(customer=obj)
        serialized_reservations = CustomerApartmentReservationSerializer(
            reservations, many=True
        ).data

        # sort reservations by
        #   1. canceled as last ones
        #   2. queue_position
        #   3. apartment number
        #   4. id
        sorted_serialized_reservations = sorted(
            serialized_reservations,
            key=lambda x: (
                x["state"] == ApartmentReservationState.CANCELED.value,
                x["queue_position"] if (x["queue_position"] is not None) else 999999,
                *get_apartment_number_sort_tuple(x["apartment_number"]),
                x["id"],
            ),
        )
        return sorted_serialized_reservations

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

    @transaction.atomic
    def update(self, obj, validated_data):
        primary_profile_data = validated_data.pop("primary_profile")
        update_obj(obj.primary_profile, primary_profile_data)

        if secondary_profile_data := validated_data.pop("secondary_profile", None):
            if obj.secondary_profile:
                update_obj(obj.secondary_profile, secondary_profile_data)
            else:
                obj.secondary_profile = Profile.objects.create(**secondary_profile_data)
        else:
            obj.secondary_profile = None

        update_obj(obj, validated_data)

        return obj


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
            "right_of_residence",
        ]

    def get_secondary_first_name(self, obj):
        if obj.secondary_profile:
            return obj.secondary_profile.first_name
        return None

    def get_secondary_last_name(self, obj):
        if obj.secondary_profile:
            return obj.secondary_profile.last_name
        return None


class CustomerCommentSerializer(serializers.ModelSerializer):
    author = ProfileSerializer(read_only=True)

    class Meta:
        model = CustomerComment
        fields = ("id", "customer", "author", "content", "created_at")
        read_only_fields = ("id", "author", "created_at", "customer")
