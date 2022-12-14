from collections import defaultdict
from datetime import timedelta
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework import serializers, status
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField
from rest_framework.response import Response

from application_form.permissions import DrupalAuthentication, IsDrupalServer
from audit_log.viewsets import AuditLoggingModelViewSet
from cost_index.api.serializers import (
    ApartmentRevaluationSerializer,
    CostIndexSerializer,
)
from cost_index.models import ApartmentRevaluation, CostIndex


class CostIndexViewSet(AuditLoggingModelViewSet):
    queryset = CostIndex.objects.all()
    serializer_class = CostIndexSerializer
    http_method_names = ("get", "post", "put", "delete")


class ApartmentRevaluationViewSet(AuditLoggingModelViewSet):
    queryset = ApartmentRevaluation.objects.all()
    serializer_class = ApartmentRevaluationSerializer

    http_method_names = ("get", "post", "put", "delete")

    def get_queryset(self):
        qs = super().get_queryset()
        apartment_uuid = self.kwargs.get("apartment_uuid")
        return qs.filter(apartment_reservation__apartment_uuid=apartment_uuid)

    @action(methods=["GET"], detail=False)
    def current(self, request):
        qs = self.get_queryset()
        return Response(ApartmentRevaluationSerializer(qs.last()).data)


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


@api_view(http_method_names=["GET"])
@require_http_methods(["GET"])  # For SonarCloud
@permission_classes([IsDrupalServer])
@authentication_classes([DrupalAuthentication])
def apartment_revaluation_summary(request):
    """
    Drupal API for retrieving changed apartment revaluations

    By default
        start_time: timezone.now() - timedelta(hours=1)
        end_time = timezone.now()
    """
    data = ApartmentRevaluationsRequest(data=request.query_params)
    data.is_valid(raise_exception=True)

    start = data.validated_data["start_time"]
    end = data.validated_data["end_time"]

    # Collect apartment uuids that fit the requested time span
    apartment_uuids = (
        ApartmentRevaluation.objects.filter(created_at__gte=start, created_at__lte=end)
        .order_by("apartment_reservation__apartment_uuid")
        .distinct("apartment_reservation__apartment_uuid")
        .values_list("apartment_reservation__apartment_uuid", flat=True)
    )

    # Collect all revaluations related to the apartment uuids
    all_revaluations = (
        ApartmentRevaluation.objects.filter(
            apartment_reservation__apartment_uuid__in=apartment_uuids
        )
        .order_by("-created_at")
        .annotate(apartment_uuid=F("apartment_reservation__apartment_uuid"))
    )
    apartments = defaultdict(lambda: {})
    for revaluation in all_revaluations:
        apartment_uuid = revaluation.apartment_uuid
        apartment = apartments[apartment_uuid]
        if not apartment:
            apartment["apartment_uuid"] = apartment_uuid
            apartment["created_at"] = revaluation.created_at
            apartment[
                "adjusted_right_of_occupancy_payment"
            ] = revaluation.end_right_of_occupancy_cost
            apartment["alteration_work_total"] = revaluation.alteration_work
        else:
            apartment["alteration_work_total"] += revaluation.alteration_work

    return Response(list(apartments.values()), status=status.HTTP_200_OK)
