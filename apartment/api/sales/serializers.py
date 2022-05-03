from rest_framework import serializers

from apartment.enums import ApartmentState
from application_form.api.sales.serializers import SalesApartmentReservationSerializer
from application_form.models import ApartmentReservation


class ApartmentSerializer(serializers.Serializer):
    apartment_uuid = serializers.UUIDField(source="uuid")
    apartment_number = serializers.CharField()
    apartment_structure = serializers.CharField()
    living_area = serializers.FloatField()
    reservations = serializers.SerializerMethodField()
    url = serializers.CharField()
    state = serializers.SerializerMethodField()

    def get_reservations(self, obj):
        reservations = ApartmentReservation.objects.filter(
            apartment_uuid=obj["uuid"]
        ).order_by(
            "list_position",
            "queue_position",
        )
        return SalesApartmentReservationSerializer(reservations, many=True).data

    def get_state(self, obj):
        try:
            winner = ApartmentReservation.objects.winners().get(apartment_uuid=obj.uuid)
        except ApartmentReservation.DoesNotExist:
            return ApartmentState.FREE.value
        except ApartmentReservation.MultipleObjectsReturned:
            return ApartmentState.REVIEW.value
        return ApartmentState.get_from_winner_reservation_state(winner.state).value
