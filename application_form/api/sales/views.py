from datetime import timedelta

from dateutil import parser
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
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
from apartment.utils import get_apartment_state_of_sale_from_event
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
    OfferMessageQueryParamsSerializer,
)
from application_form.api.views import ApplicationViewSet
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.exceptions import ProjectDoesNotHaveApplicationsException
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    LotteryEvent,
    Offer,
)
from application_form.pdf import (
    create_haso_contract_pdf,
    create_haso_release_pdf,
    create_hitas_contract_pdf,
)
from application_form.permissions import DrupalAuthentication, IsDrupalServer
from application_form.services.application import cancel_reservation
from application_form.services.lottery.exceptions import (
    ApplicationTimeNotFinishedException,
)
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import _adjust_positions
from application_form.services.reservation import (
    transfer_reservation_to_another_customer,
)
from audit_log.viewsets import AuditLoggingModelViewSet
from users.permissions import IsDjangoSalesperson, IsDrupalSalesperson


@api_view(http_method_names=["POST"])
@permission_classes([IsDjangoSalesperson])
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
        distribute_apartments(project_uuid, request.user)
    except ProjectDoesNotHaveApplicationsException as ex:
        raise ValidationError(detail="Project does not have applications.") from ex
    except ApplicationTimeNotFinishedException as ex:
        raise ValidationError(detail=str(ex)) from ex

    return Response({"status": "success"}, status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
@require_http_methods(["GET"])  # For SonarCloud
@permission_classes([IsDrupalServer])
@authentication_classes([DrupalAuthentication])
def apartment_states(request):
    """
    Returns ids and latest states of distributed apartments changed during start_time
    and end_time
    By default
        start_time: timezone.now() - timedelta(hours=1)
        end_time = timezone.now()
    """
    end_time_obj = timezone.now()
    start_time_obj = end_time_obj - timedelta(
        hours=settings.DEFAULT_SOLD_APARMENT_TIME_RANGE
    )
    try:
        if start_time := request.query_params.get("start_time"):
            start_time_obj = parser.isoparse(start_time)
        if end_time := request.query_params.get("end_time"):
            end_time_obj = parser.isoparse(end_time)
    except ValueError:
        raise ValidationError(
            "Invalid datetime format, "
            "the correct format is - `YYYY-MM-DD'T'hh:mm:ss` or "
            "`YYYYMMDD'T'hhmmss`"
        )

    if start_time_obj > end_time_obj:
        raise ValidationError(
            f"Start date {start_time_obj} cannot be greater than "
            f"end date {end_time_obj}"
        )

    # Select the latest state event of apartments that have been distributed
    state_events = (
        ApartmentReservationStateChangeEvent.objects.filter(
            timestamp__range=[start_time_obj, end_time_obj],
            reservation__apartment_uuid__in=LotteryEvent.objects.values(
                "apartment_uuid"
            ),
        )
        .select_related("reservation")
        .order_by("reservation__apartment_uuid", "-timestamp")
        .distinct("reservation__apartment_uuid")
    )

    results = {
        str(e.reservation.apartment_uuid): get_apartment_state_of_sale_from_event(e)
        for e in state_events
    }

    return Response(results, status=status.HTTP_200_OK)


class SalesApplicationViewSet(ApplicationViewSet):
    serializer_class = SalesApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsDrupalSalesperson]


class ApartmentReservationViewSet(
    mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = ApartmentReservation.objects.select_related("offer").prefetch_related(
        "apartment_installments", "apartment_installments__payments"
    )
    serializer_class = RootApartmentReservationSerializer

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
        title = (
            (apartment.title or "").strip().lower().replace(" ", "_").replace(",", "")
        )

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
        description="Create HASO apartment release PDF",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(methods=["GET"], detail=True)
    def release_pdf(self, request, **kwargs):
        reservation = self.get_object()
        apartment = get_apartment(
            reservation.apartment_uuid, include_project_fields=True
        )

        if apartment.project_ownership_type.lower() != "haso":
            raise ValidationError("Apartment ownership type is not HASO")

        if not hasattr(reservation, "revaluation"):
            raise ValidationError("Reservation has no revaluation")

        title = (
            (apartment.title or "").strip().lower().replace(" ", "_").replace(",", "")
        )
        filename = f"haso_luovutuslaskelma{title}" if title else "haso_luovutuslaskelma"

        pdf_data = create_haso_release_pdf(
            request.user.profile_or_user_full_name, reservation
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

        queue_position = state_change_event_serializer.validated_data.get(
            "queue_position", None
        )
        if (
            queue_position is None
            and reservation.queue_position_before_cancelation is not None
        ):
            queue_position = reservation.queue_position_before_cancelation

        new_state = state_change_event_serializer.validated_data.get("state")

        if (
            queue_position is not None
            and new_state != ApartmentReservationState.CANCELED
        ):
            # conver queue_position from string to number
            if isinstance(queue_position, str):
                queue_position = int(queue_position.lstrip("0"))

            current_queue_length = (
                ApartmentReservation.objects.active()
                .filter(apartment_uuid=reservation.apartment_uuid)
                .count()
            )

            if queue_position > current_queue_length:
                queue_position = current_queue_length + 1

            # position correction in queue
            _adjust_positions(
                ApartmentReservation.objects.filter(
                    apartment_uuid=reservation.apartment_uuid
                ),
                "queue_position",
                queue_position,
                by=1,
            )

        # set state and position
        state_change_event = reservation.set_state(
            **state_change_event_serializer.validated_data,
            user=request.user,
        )

        if (
            queue_position is not None
            and new_state != ApartmentReservationState.CANCELED
        ):
            # save new position to database
            reservation.queue_position = queue_position
            reservation.save(update_fields=["queue_position"])

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
        parameters=[
            OpenApiParameter("valid_until", OpenApiTypes.DATE, OpenApiParameter.QUERY)
        ],
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

        query_params_serializer = OfferMessageQueryParamsSerializer(
            data=request.query_params
        )
        query_params_serializer.is_valid(raise_exception=True)

        return Response(
            OfferMessageSerializer(
                reservation,
                context={
                    "valid_until": query_params_serializer.validated_data.get(
                        "valid_until"
                    )
                },
            ).data,
            status=status.HTTP_200_OK,
        )


class OfferViewSet(AuditLoggingModelViewSet):
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    http_method_names = ["get", "post", "put", "patch"]

    def list(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class ProjectExtraDataViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ProjectExtraData.objects.all()
    serializer_class = ProjectExtraDataSerializer
