from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField, DecimalField

from cost_index.models import ApartmentRevaluation, CostIndex
from cost_index.utils import determine_date_index


class CostIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostIndex
        fields = ("id", "valid_from", "value")


class ApartmentRevaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApartmentRevaluation
        fields = "__all__"

    def validate(self, attrs):

        valid_start_cost_index = determine_date_index(attrs["start_date"])
        valid_end_cost_index = determine_date_index(attrs["end_date"])

        if valid_start_cost_index != attrs["start_cost_index_value"]:
            raise ValidationError("Requested cost index does not match start_date")

        if valid_end_cost_index != attrs["end_cost_index_value"]:
            raise ValidationError("Requested cost index does not match end_date")

        return attrs


class ApartmentRevaluationsRequest(serializers.Serializer):
    start_time = DateTimeField(required=False, allow_null=True, default=None)
    end_time = DateTimeField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")

        if not end:
            end = timezone.now()
            attrs["end_time"] = end

        if not start:
            start = end - timedelta(
                hours=settings.DEFAULT_APARTMENT_REVALUATION_TIME_RANGE
            )
            attrs["start_time"] = start

        if start >= end:
            raise ValidationError("start_time must be less than end_time")

        return attrs


class ApartmentRightOfOccupancyPaymentSerializer(serializers.Serializer):
    right_of_occupancy_payment = DecimalField(max_digits=16, decimal_places=2)
    current_right_of_occupancy_payment = DecimalField(max_digits=16, decimal_places=2)
