from rest_framework import serializers
from uuid import UUID

from apartment.utils import get_apartment_state
from application_form.api.sales.serializers import (
    SalesWinningApartmentReservationSerializer,
)


class ApartmentSerializer(serializers.Serializer):
    apartment_uuid = serializers.UUIDField(source="uuid")
    apartment_number = serializers.CharField()
    apartment_structure = serializers.CharField()
    living_area = serializers.FloatField()
    url = serializers.CharField()
    state = serializers.SerializerMethodField()
    reservation_count = serializers.SerializerMethodField()
    winning_reservation = serializers.SerializerMethodField()

    def get_state(self, obj):
        return get_apartment_state(obj.uuid)

    def get_reservation_count(self, obj):
        return next(
            (
                apartment["reservation_count"]
                for apartment in self.context["reservation_counts"]
                if apartment["apartment_uuid"] == UUID(obj.uuid)
            ),
            0,
        )

    def get_winning_reservation(self, obj):
        winning_reservation = next(
            (
                reservation
                for reservation in self.context["winning_reservations"]
                if reservation.apartment_uuid == UUID(obj.uuid)
            ),
            None,
        )

        return (
            SalesWinningApartmentReservationSerializer(
                winning_reservation,
                context={"project_uuid": self.context["project_uuid"]},
            ).data
            if winning_reservation
            else None
        )
