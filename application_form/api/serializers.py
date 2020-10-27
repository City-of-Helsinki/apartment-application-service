from rest_framework import serializers

from application_form.models import (
    Apartment,
    HasoApartmentPriority,
    HasoApplication,
    HitasApplication,
)


class HasoSerializer(serializers.ModelSerializer):
    apartment_uuids = serializers.ListField(child=serializers.UUIDField())

    class Meta:
        model = HasoApplication
        fields = [
            "apartment_uuids",
            "is_approved",
            "is_rejected",
            "rejection_description",
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
        self.create_or_update_apartments_and_priorities(
            apartment_uuids, haso_application
        )
        return haso_application

    def update(self, instance, validated_data):
        apartment_uuids = validated_data.pop("apartment_uuids")
        haso_application = super(HasoSerializer, self).update(instance, validated_data)
        self.create_or_update_apartments_and_priorities(
            apartment_uuids, haso_application
        )
        return haso_application

    def create_or_update_apartments_and_priorities(
        self, apartment_uuids, haso_application
    ):
        # Here we assume that the apartment_uuids list is already in the
        # prioritized order.
        for idx, apartment_uuid in enumerate(apartment_uuids):
            apartment, _ = Apartment.objects.get_or_create(
                apartment_uuid=apartment_uuid,
            )
            HasoApartmentPriority.objects.get_or_create(
                priority_number=idx,
                apartment=apartment,
                haso_application=haso_application,
            )


class HitasSerializer(serializers.ModelSerializer):
    apartment_uuid = serializers.UUIDField(source="apartment.apartment_uuid")

    class Meta:
        model = HitasApplication
        fields = [
            "apartment_uuid",
            "is_approved",
            "is_rejected",
            "rejection_description",
            "applicant_has_accepted_offer",
            "has_previous_hitas_apartment",
            "previous_hitas_description",
            "has_children",
        ]

    def create(self, validated_data):
        self.update_validated_data_with_apartment(validated_data)
        return super(HitasSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        self.update_validated_data_with_apartment(validated_data)
        return super(HitasSerializer, self).update(instance, validated_data)

    def update_validated_data_with_apartment(self, validated_data):
        apartment_uuid = validated_data.pop("apartment")["apartment_uuid"]
        apartment, _ = Apartment.objects.get_or_create(
            apartment_uuid=apartment_uuid,
        )
        validated_data["apartment"] = apartment
