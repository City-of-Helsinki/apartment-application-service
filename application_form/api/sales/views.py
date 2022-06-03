from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apartment.elastic.queries import get_apartment, get_project
from apartment.models import ProjectExtraData
from application_form.api.sales.serializers import (
    OfferMessageSerializer,
    OfferSerializer,
    ProjectExtraDataSerializer,
    ProjectUUIDSerializer,
    RootApartmentReservationSerializer,
    SalesApplicationSerializer,
)
from application_form.api.serializers import (
    ApartmentReservationCancelEventSerializer,
    ApartmentReservationStateChangeEventSerializer,
)
from application_form.api.views import ApplicationViewSet
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.exceptions import ProjectDoesNotHaveApplicationsException
from application_form.models import ApartmentReservation, Offer
from application_form.pdf import create_haso_contract_pdf, create_hitas_contract_pdf
from application_form.services.application import cancel_reservation
from application_form.services.lottery.exceptions import (
    ApplicationTimeNotFinishedException,
)
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.reservation import (
    transfer_reservation_to_another_customer,
)
from users.permissions import IsSalesperson


@api_view(http_method_names=["POST"])
@permission_classes([permissions.AllowAny])
@authentication_classes([])
@require_http_methods(["POST"])  # For SonarCloud
def execute_lottery_for_project(request):
    """
    Run the lottery for the given project.
    """
    serializer = ProjectUUIDSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    project_uuid = serializer.data.get("project_uuid")

    try:
        get_project(project_uuid)
    except ObjectDoesNotExist:
        raise NotFound(detail="Project not found.")

    try:
        distribute_apartments(project_uuid)
    except ProjectDoesNotHaveApplicationsException as ex:
        raise ValidationError(detail="Project does not have applications.") from ex
    except ApplicationTimeNotFinishedException as ex:
        raise ValidationError(detail=str(ex)) from ex

    return Response({"status": "success"}, status=status.HTTP_200_OK)


class SalesApplicationViewSet(ApplicationViewSet):
    serializer_class = SalesApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsSalesperson]


class ApartmentReservationViewSet(
    mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = ApartmentReservation.objects.select_related("offer")
    serializer_class = RootApartmentReservationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        description="Create either a Hitas contract or a HASO contract PDF based on "
        "the reservation's project's ownership type.",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(methods=["GET"], detail=True)
    def contract(self, request, pk=None):
        reservation = self.get_object()
        apartment = get_apartment(
            reservation.apartment_uuid, include_project_fields=True
        )
        title = (apartment.title or "").strip().lower().replace(" ", "_")

        ownership_type = apartment.project_ownership_type.lower()
        if ownership_type == "hitas":
            filename = f"hitas_sopimus_{title}" if title else "hitas_sopimus"
            pdf_data = create_hitas_contract_pdf(reservation)
        elif ownership_type == "haso":
            filename = f"haso_sopimus_{title}" if title else "haso_sopimus"
            pdf_data = create_haso_contract_pdf(reservation)
        else:
            raise ValueError(
                f"Unknown ownership_type: {apartment.project_ownership_type}"
            )

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={filename}.pdf"

        return response

    @extend_schema(
        operation_id="sales_apartment_reservations_set_state",
        request=ApartmentReservationStateChangeEventSerializer,
        responses={
            (200, "application/json"): ApartmentReservationStateChangeEventSerializer
        },
    )
    @action(methods=["POST"], detail=True)
    def set_state(self, request, pk=None):
        reservation = self.get_object()
        data = {"reservation_id": pk}
        data.update(request.data)

        state_change_event_serializer = ApartmentReservationStateChangeEventSerializer(
            data=data
        )
        state_change_event_serializer.is_valid(raise_exception=True)

        state_change_event = reservation.set_state(
            **state_change_event_serializer.validated_data,
            user=request.user,
        )

        return Response(
            ApartmentReservationStateChangeEventSerializer(state_change_event).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id="sales_apartment_reservations_cancel",
        request=ApartmentReservationCancelEventSerializer,
        responses={
            (200, "application/json"): ApartmentReservationCancelEventSerializer
        },
        examples=[
            OpenApiExample(
                "Cancel Example",
                value={
                    "comment": "Lorem ipsum.",
                    "cancellation_reason": "terminated",
                },
            ),
            OpenApiExample(
                "Transfer Example",
                value={
                    "comment": "Lorem ipsum.",
                    "cancellation_reason": "transferred",
                    "new_customer_id": 7,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Transfer Example",
                value={
                    "comment": "Lorem ipsum.",
                    "cancellation_reason": "transferred",
                    "new_customer_id": 7,
                    "new_reservation_id": 8,
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=["POST"], detail=True)
    def cancel(self, request, pk=None):
        reservation = self.get_object()

        if reservation.state == ApartmentReservationState.CANCELED:
            raise ValidationError("This reservation is already canceled.")

        data = {"reservation_id": pk}
        data.update(request.data)

        cancel_event_serializer = ApartmentReservationCancelEventSerializer(data=data)
        cancel_event_serializer.is_valid(raise_exception=True)

        if (
            cancel_event_serializer.validated_data["cancellation_reason"]
            == ApartmentReservationCancellationReason.TRANSFERRED
        ):
            cancel_event_serializer.validated_data.pop("cancellation_reason")
            cancel_event = transfer_reservation_to_another_customer(
                reservation,
                user=request.user,
                **cancel_event_serializer.validated_data,
            )
        else:
            cancel_event = cancel_reservation(
                reservation,
                user=request.user,
                **cancel_event_serializer.validated_data,
            )

        return Response(
            ApartmentReservationCancelEventSerializer(cancel_event).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses=OfferMessageSerializer(),
        examples=[
            OpenApiExample(
                "Offer message example",
                value={
                    "subject": "Tarjous As Oy Pojanlohi C4",
                    "body": """Lorem ipsum

Huoneisto: C4
Huoneistotyyppi: 5h+k

Ipsum
Lorem
""".replace(
                        "\n", "\r\n"
                    ),
                    "recipients": [
                        {"name": "Ulla Taalasmaa", "email": "ulla@example.com"},
                        {"name": "Suppo Taalasmaa", "email": "suppo@example.com"},
                    ],
                },
            ),
        ],
    )
    @action(methods=["GET"], detail=True)
    def offer_message(self, request, pk=None):
        reservation = self.get_object()
        return Response(
            OfferMessageSerializer(reservation).data, status=status.HTTP_200_OK
        )


class OfferViewSet(
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer


class ProjectExtraDataViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ProjectExtraData.objects.all()
    serializer_class = ProjectExtraDataSerializer
