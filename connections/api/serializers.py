from rest_framework import serializers

from connections.models import MappedApartment


class MappedApartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MappedApartment
        fields = "__all__"
