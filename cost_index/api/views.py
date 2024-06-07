from django.db.models import F
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apartment.elastic.queries import get_apartment
from application_form.permissions import DrupalAuthentication, IsDrupalServer
from audit_log.viewsets import AuditLoggingModelViewSet
from cost_index.api.serializers import (
    ApartmentRevaluationSerializer,
    ApartmentRevaluationsRequest,
    ApartmentRightOfOccupancyPaymentSerializer,
    CostIndexSerializer,
)
from cost_index.models import ApartmentRevaluation, CostIndex
from invoicing.utils import get_euros_from_cents


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
        if self.action == "list" and "apartment_uuid" in self.kwargs:
            qs = qs.filter(
                apartment_reservation__apartment_uuid=self.kwargs["apartment_uuid"]
            )
        return qs

    @action(methods=["GET"], detail=False)
    def current(self, request):
        qs = self.get_queryset()
        return Response(ApartmentRevaluationSerializer(qs.last()).data)


class ApartmentRightOfOccupancyPaymentAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request, apartment_uuid):
        apartment = get_apartment(apartment_uuid, True)
        if apartment.project_ownership_type.upper() != "HASO":
            raise ValidationError(
                "Right of occupancy payment is valid only for HASO projects "
                f"(got '{apartment.project_ownership_type}')"
            )

        data = {
            "right_of_occupancy_payment": get_euros_from_cents(
                apartment.right_of_occupancy_payment
            ),
            "current_right_of_occupancy_payment": get_euros_from_cents(
                apartment.current_right_of_occupancy_payment
            ),
        }
        serializer = ApartmentRightOfOccupancyPaymentSerializer(data)
        return Response(serializer.data)


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

    latest_revaluations = (
        ApartmentRevaluation.objects.filter(updated_at__gte=start, updated_at__lte=end)
        .annotate(apartment_uuid=F("apartment_reservation__apartment_uuid"))
        .order_by("apartment_uuid", "-end_date")
        .distinct("apartment_uuid")
    )

    apartments = {}

    for revaluation in latest_revaluations:
        apartment_uuid = revaluation.apartment_uuid
        right_of_occupancy_payment_adjustment = (
            revaluation.end_right_of_occupancy_payment
            - revaluation.start_right_of_occupancy_payment
        )
        release_payment = (
            revaluation.end_right_of_occupancy_payment + revaluation.alteration_work
        )
        apartment = get_apartment(apartment_uuid, False)
        right_of_occupancy_payment = get_euros_from_cents(
            apartment.right_of_occupancy_payment
        )
        # fmt: off
        apartments[apartment_uuid] = {
            "apartment_uuid": apartment_uuid,
            "created_at": revaluation.created_at,
            "updated_at": revaluation.updated_at,
            "alteration_work_total": revaluation.alteration_work,
            "right_of_occupancy_payment_adjustment":
                right_of_occupancy_payment_adjustment,
            "release_payment": release_payment,
            "right_of_occupancy_payment": right_of_occupancy_payment,
        }
        # fmt: on

    return Response(list(apartments.values()), status=status.HTTP_200_OK)
