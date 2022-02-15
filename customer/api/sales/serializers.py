from rest_framework import serializers

from customer.models import Customer
from users.api.sales.serializers import ProfileSerializer


class CustomerSerializer(serializers.ModelSerializer):
    primary_profile = ProfileSerializer()
    secondary_profile = ProfileSerializer()

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
        )


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
