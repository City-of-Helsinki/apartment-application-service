from rest_framework import serializers

from cost_index.models import ApartmentRevaluation, CostIndex


class CostIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostIndex
        fields = ("id", "valid_from", "value")


class ApartmentRevaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApartmentRevaluation
        fields = "__all__"
