from rest_framework import serializers

from cost_index.models import CostIndex


class CostIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostIndex
        fields = ("id", "valid_from", "value")
