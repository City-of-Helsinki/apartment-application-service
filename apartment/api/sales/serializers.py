from rest_framework import serializers

from application_form.api.sales.serializers import SalesApartmentReservationSerializer
from application_form.models import ApartmentReservation


class ApartmentSerializer(serializers.Serializer):
    apartment_uuid = serializers.UUIDField(source="uuid")
    apartment_number = serializers.CharField()
    apartment_structure = serializers.CharField()
    living_area = serializers.FloatField()
    reservations = serializers.SerializerMethodField()
    url = serializers.CharField()

    def get_reservations(self, obj):
        reservations = ApartmentReservation.objects.filter(
            apartment_uuid=obj["uuid"]
        ).order_by(
            "list_position",
            "queue_position",
        )
        return SalesApartmentReservationSerializer(
            reservations,
            many=True,
            context={"project_uuid": self.context["project_uuid"]},
        ).data
