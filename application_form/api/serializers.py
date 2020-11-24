from rest_framework import serializers

from application_form.models import HasoApplication, HitasApplication
from application_form.services import (
    create_or_update_apartments_and_priorities,
    get_or_create_apartment_with_uuid,
)


class HasoSerializer(serializers.ModelSerializer):
    # List of apartment UUIDs that can be created as apartments / queried from apartments for sending
    apartment_uuids = serializers.ListField(child=serializers.UUIDField())

    class Meta:
        model = HasoApplication
        fields = [
            "apartment_uuids",
            "is_approved",
            "is_rejected",
            "rejection_description",
            "applicant_token",
            "applicant_has_accepted_offer",
            "right_of_occupancy_id",
            "current_housing",
            "housing_description",
            "housing_type",
            "housing_area",
            "is_changing_occupancy_apartment",
            "is_over_55",
        ]

    def create(self, validated_data):
        apartment_uuids = validated_data.pop("apartment_uuids")
        haso_application = super(HasoSerializer, self).create(validated_data)
        # Apartments and priorities need to be created separately.
        create_or_update_apartments_and_priorities(apartment_uuids, haso_application)
        return haso_application

    def update(self, instance, validated_data):
        apartment_uuids = validated_data.pop("apartment_uuids")
        haso_application = super(HasoSerializer, self).update(instance, validated_data)
        # Apartments and priorities need to be updated separately.
        create_or_update_apartments_and_priorities(apartment_uuids, haso_application)
        return haso_application


class HitasSerializer(serializers.ModelSerializer):
    # Apartment UUID that can be created as an apartment / queried from apartments for sending
    apartment_uuid = serializers.UUIDField(source="apartment.apartment_uuid")

    class Meta:
        model = HitasApplication
        fields = [
            "apartment_uuid",
            "is_approved",
            "is_rejected",
            "rejection_description",
            "applicant_token",
            "applicant_has_accepted_offer",
            "has_previous_hitas_apartment",
            "previous_hitas_description",
            "has_children",
        ]

    def create(self, validated_data):
        apartment_uuid = validated_data.pop("apartment")["apartment_uuid"]
        # Apartments need to be created separately.
        apartment = get_or_create_apartment_with_uuid(apartment_uuid)
        validated_data["apartment"] = apartment
        return super(HitasSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        apartment_uuid = validated_data.pop("apartment")["apartment_uuid"]
        # Apartments need to be updated separately.
        apartment = get_or_create_apartment_with_uuid(apartment_uuid)
        validated_data["apartment"] = apartment
        return super(HitasSerializer, self).update(instance, validated_data)
