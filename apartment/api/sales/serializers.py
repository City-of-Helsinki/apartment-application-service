from rest_framework import serializers

from apartment.utils import get_apartment_state
from application_form.api.sales.serializers import SalesApartmentReservationSerializer


class ApartmentSerializer(serializers.Serializer):
    apartment_uuid = serializers.UUIDField(source="uuid")
    apartment_number = serializers.CharField()
    apartment_structure = serializers.CharField()
    living_area = serializers.FloatField()
    reservations = serializers.SerializerMethodField()
    url = serializers.CharField()
    state = serializers.SerializerMethodField()

    def get_reservations(self, obj):
        reservations = []
        if self.context.get("reservations"):
            reservations = sorted(
                [
                    r
                    for r in self.context.get("reservations")
                    if str(r.apartment_uuid) == obj.uuid
                ],
                key=lambda x: x.list_position,
            )

        return SalesApartmentReservationSerializer(
            reservations,
            many=True,
            context={"project_uuid": self.context["project_uuid"]},
        ).data

    def get_state(self, obj):
        return get_apartment_state(obj.uuid)
