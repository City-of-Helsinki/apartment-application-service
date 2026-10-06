import logging
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from typing import Optional

from dateutil import parser
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
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

from apartment.elastic.queries import (
    get_apartment,
    get_apartments_for_uuids,
    get_project,
)
from apartment.models import ProjectExtraData
from apartment.utils import get_apartment_state_of_sale_from_event
from application_form.api.sales.serializers import (
    OfferMessageSerializer,
    OfferSerializer,
    ProjectExtraDataSerializer,
    ProjectUUIDSerializer,
    ReservationMessageCreateSerializer,
    ReservationMessageInboxSummarySerializer,
    ReservationMessageSerializer,
    ReservationMessageThreadSerializer,
    ReservationMessageUnreadCountsSerializer,
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
from application_form.services.drupal_messaging import (
    DrupalMessagingClient,
    DrupalMessagingClientError,
)
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


def _build_no_cache_response(data, status_code=status.HTTP_200_OK):
    """Return an API response with disabled caching for unread counters."""
    response = Response(data, status=status_code)
    response["Cache-Control"] = "no-store, no-cache, private"
    return response


def _empty_unread_counts() -> dict:
    """Return the fallback unread payload for sales UI."""
    return {"counts": {}, "total": 0}


def _empty_inbox_summary() -> dict:
    """Return the fallback inbox summary payload for sales UI."""
    return {"items": [], "total_unread": 0}


def _build_unread_counts_error_response(exc: DrupalMessagingClientError) -> Response:
    """Map unread integration errors into stable sales API responses."""
    if exc.status_code == 404:
        _logger.info("Unread counts not found in Drupal. Returning empty payload.")
        return _build_no_cache_response(_empty_unread_counts())
    if (
        exc.status_code == 403
        or exc.status_code >= 500
        or exc.code in {"temporary_failure", "forbidden"}
    ):
        _logger.warning(
            "Unread counts fallback due to Drupal error: status=%s code=%s",
            exc.status_code,
            exc.code,
        )
        return _build_no_cache_response(_empty_unread_counts())
    return _build_no_cache_response(
        {"detail": "Messaging service temporarily unavailable."},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _build_inbox_summary_error_response(exc: DrupalMessagingClientError) -> Response:
    """Map inbox summary integration errors into stable sales API responses."""
    if exc.status_code == 404:
        _logger.info("Inbox summary not found in Drupal. Returning empty payload.")
        return _build_no_cache_response(_empty_inbox_summary())
    if (
        exc.status_code == 403
        or exc.status_code >= 500
        or exc.code in {"temporary_failure", "forbidden"}
    ):
        _logger.warning(
            "Inbox summary fallback due to Drupal error: status=%s code=%s",
            exc.status_code,
            exc.code,
        )
        return _build_no_cache_response(_empty_inbox_summary())
    return _build_no_cache_response(
        {"detail": "Messaging service temporarily unavailable."},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _get_sales_unread_application_ids() -> list[int]:
    """Return active Drupal application ids for legacy unread contract fallback."""
    return list(
        ApartmentReservation.objects.active()
        .filter(
            application_apartment__application__drupal_application_id__isnull=False,
        )
        .values_list(
            "application_apartment__application__drupal_application_id",
            flat=True,
        )
        .distinct()
        .order_by("application_apartment__application__drupal_application_id")
    )


def _get_sales_reservations_for_drupal_application_ids(
    drupal_application_ids: list[int],
):
    """Return active reservations linked to the given Drupal application ids."""
    if not drupal_application_ids:
        return ApartmentReservation.objects.none()

    return (
        ApartmentReservation.objects.active()
        .filter(
            application_apartment__application__drupal_application_id__in=(
                drupal_application_ids
            ),
        )
        .select_related("application_apartment__application")
        .order_by("application_apartment__application__drupal_application_id", "id")
    )


def _fetch_apartments_by_uuid_for_summary(
    apartment_uuid_by_application_id: dict[int, str],
) -> dict[str, dict]:
    """Fetch apartment documents with fallback to per-apartment requests."""
    if not apartment_uuid_by_application_id:
        return {}

    try:
        return get_apartments_for_uuids(
            apartment_uuid_by_application_id.values(),
            include_project_fields=True,
        )
    except ObjectDoesNotExist:
        apartments_by_uuid = {}
        for apartment_uuid in set(apartment_uuid_by_application_id.values()):
            try:
                apartments_by_uuid[apartment_uuid] = get_apartment(
                    apartment_uuid,
                    include_project_fields=True,
                )
            except ObjectDoesNotExist:
                _logger.info(
                    "Inbox context enrichment skipped for apartment uuid=%s",
                    apartment_uuid,
                )
        return apartments_by_uuid


def _get_sales_inbox_summary_context_by_drupal_application_id(
    drupal_application_ids: list[int],
) -> dict[int, dict]:
    """Build per-application inbox context required for stable deep-links."""
    reservations = _get_sales_reservations_for_drupal_application_ids(
        drupal_application_ids
    )

    first_reservation_by_application_id: dict[int, ApartmentReservation] = {}
    apartment_uuid_by_application_id: dict[int, str] = {}
    applicant_names: dict[int, str] = {}
    for reservation in reservations:
        application = reservation.application_apartment.application
        drupal_application_id = application.drupal_application_id
        if drupal_application_id is None:
            continue

        candidate_name = application.sender_names or ""
        if drupal_application_id not in applicant_names:
            applicant_names[drupal_application_id] = candidate_name
        elif not applicant_names[drupal_application_id] and candidate_name:
            applicant_names[drupal_application_id] = candidate_name

        if drupal_application_id in first_reservation_by_application_id:
            continue

        first_reservation_by_application_id[drupal_application_id] = reservation
        apartment_uuid_by_application_id[drupal_application_id] = str(
            reservation.apartment_uuid
        )

    if not first_reservation_by_application_id:
        return {}

    apartments_by_uuid = _fetch_apartments_by_uuid_for_summary(
        apartment_uuid_by_application_id
    )

    context_by_application_id: dict[int, dict] = {}
    for application_id, reservation in first_reservation_by_application_id.items():
        apartment_uuid = apartment_uuid_by_application_id.get(application_id)
        apartment = apartments_by_uuid.get(apartment_uuid)
        context_by_application_id[application_id] = {
            "customer_id": reservation.customer_id,
            "project_uuid": str(apartment.project_uuid) if apartment else None,
            "reservation_id": reservation.id,
            "project_id": apartment.project_id if apartment else None,
            "project_name": (
                (apartment.project_housing_company or "") if apartment else ""
            ),
            "applicant_name": applicant_names.get(application_id, ""),
        }

    return context_by_application_id


def _extract_inbox_summary_application_ids(raw_items: list) -> list[int]:
    """Extract valid numeric application ids from inbox summary payload items."""
    application_ids: list[int] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            application_id = int(item.get("application_id"))
        except (TypeError, ValueError):
            continue
        application_ids.append(application_id)
    return application_ids


def _is_unread_inbox_item(item: dict) -> bool:
    """Return whether an inbox summary item should be included as unread."""
    unread_count_value = item.get("unread_count", 0)
    try:
        unread_count = int(unread_count_value)
    except (TypeError, ValueError):
        unread_count = 0

    has_unread = bool(item.get("has_unread"))
    return unread_count > 0 or has_unread


def _has_required_deep_link_context(item: dict) -> bool:
    """Return whether required deep-link identifiers are present."""
    return bool(
        item.get("customer_id")
        and item.get("project_uuid")
        and item.get("reservation_id")
    )


def _enrich_inbox_summary_payload(payload: dict) -> dict:
    """Enrich inbox summary items with local deep-link identifiers."""
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        return payload

    application_ids = _extract_inbox_summary_application_ids(raw_items)

    summary_context = _get_sales_inbox_summary_context_by_drupal_application_id(
        application_ids
    )
    enriched_items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        enriched_item = dict(item)
        try:
            application_id = int(enriched_item.get("application_id"))
        except (TypeError, ValueError):
            application_id = None
        context = summary_context.get(application_id, {}) if application_id else {}
        enriched_item["customer_id"] = context.get("customer_id")
        enriched_item["project_uuid"] = context.get("project_uuid")
        enriched_item["reservation_id"] = context.get("reservation_id")
        enriched_item["project_id"] = context.get("project_id")
        enriched_item["project_name"] = context.get("project_name", "")
        enriched_item["applicant_name"] = context.get("applicant_name", "")

        if not _is_unread_inbox_item(enriched_item):
            continue

        if not _has_required_deep_link_context(enriched_item):
            _logger.warning(
                "Inbox summary item skipped due to missing deep-link context. "
                "application_id=%s",
                application_id,
            )
            continue

        enriched_items.append(enriched_item)

    enriched_payload = dict(payload)
    enriched_payload["items"] = enriched_items
    enriched_payload["total_unread"] = sum(
        int(item.get("unread_count", 0)) for item in enriched_items
    )
    return enriched_payload


@extend_schema(
    operation_id="sales_application_unread_counts",
    responses={(200, "application/json"): ReservationMessageUnreadCountsSerializer},
)
@api_view(http_method_names=["GET"])
@require_http_methods(["GET"])  # For SonarCloud
@permission_classes([IsDrupalSalesperson])
def application_unread_counts(request):
    """Return unread message counts for sales users."""
    client = DrupalMessagingClient()

    try:
        payload = client.get_unread_counts(viewer_role="sales")
    except DrupalMessagingClientError as exc:
        if exc.code == "invalid_request" or exc.status_code == 400:
            _logger.info(
                "Unread counts retrying with application_ids due to legacy "
                "Drupal contract. status=%s code=%s",
                exc.status_code,
                exc.code,
            )
            application_ids = _get_sales_unread_application_ids()
            try:
                payload = client.get_unread_counts(
                    viewer_role="sales",
                    application_ids=application_ids,
                )
            except DrupalMessagingClientError as retry_exc:
                return _build_unread_counts_error_response(retry_exc)
        else:
            return _build_unread_counts_error_response(exc)

    serializer = ReservationMessageUnreadCountsSerializer(data=payload)
    if not serializer.is_valid():
        _logger.warning(
            "Unread counts payload validation failed. Returning empty payload. "
            "errors=%s",
            serializer.errors,
        )
        return _build_no_cache_response(_empty_unread_counts())

    return _build_no_cache_response(serializer.validated_data)


@extend_schema(
    operation_id="sales_application_inbox_summary",
    responses={(200, "application/json"): ReservationMessageInboxSummarySerializer},
)
@api_view(http_method_names=["GET"])
@require_http_methods(["GET"])  # For SonarCloud
@permission_classes([IsDrupalSalesperson])
def application_inbox_summary(request):
    """Return inbox summary for sales users in shared unread mode."""
    client = DrupalMessagingClient()

    try:
        payload = client.get_inbox_summary(viewer_role="sales")
    except DrupalMessagingClientError as exc:
        if exc.code == "invalid_request" or exc.status_code == 400:
            _logger.info(
                "Inbox summary retrying with application_ids due to legacy "
                "Drupal contract. status=%s code=%s",
                exc.status_code,
                exc.code,
            )
            application_ids = _get_sales_unread_application_ids()
            try:
                payload = client.get_inbox_summary(
                    viewer_role="sales",
                    application_ids=application_ids,
                )
            except DrupalMessagingClientError as retry_exc:
                return _build_inbox_summary_error_response(retry_exc)
        else:
            return _build_inbox_summary_error_response(exc)

    payload = _enrich_inbox_summary_payload(payload)
    serializer = ReservationMessageInboxSummarySerializer(data=payload)
    if not serializer.is_valid():
        _logger.warning(
            "Inbox summary payload validation failed. Returning empty payload. "
            "errors=%s",
            serializer.errors,
        )
        return _build_no_cache_response(_empty_inbox_summary())

    return _build_no_cache_response(serializer.validated_data)


def _recalculate_queue_position_for_haso_on_submitted_late_change(
    *,
    reservation,
    new_state,
) -> Optional[int]:
    """
    - If the client didn't explicitly provide queue_position, HASO ordering is
      recalculated when submitted_late changes.
    - Returns None when recalculation isn't possible (e.g. no right of residence).
    """
    if new_state == ApartmentReservationState.CANCELED:
        return None
    if reservation.queue_position is None:
        return None

    apartment = get_apartment(reservation.apartment_uuid, include_project_fields=True)
    if (apartment.project_ownership_type or "").lower() != "haso":
        return None

    ordering_number = reservation.right_of_residence_ordering_number
    if ordering_number is None:
        return None

    active_qs = ApartmentReservation.objects.active().filter(
        apartment_uuid=reservation.apartment_uuid
    )
    if reservation.pk:
        active_qs = active_qs.exclude(pk=reservation.pk)

    current_queue_length = active_qs.count()
    queue_position = current_queue_length + 1
    offered_or_sold_states = {
        ApartmentReservationState.OFFER_ACCEPTED,
        ApartmentReservationState.OFFERED,
        ApartmentReservationState.SOLD,
    }

    same_late_group = active_qs.filter(
        submitted_late=reservation.submitted_late
    ).order_by("queue_position")
    for other in same_late_group:
        other_ordering_number = other.right_of_residence_ordering_number
        if (
            other_ordering_number is not None
            and ordering_number < other_ordering_number
            and other.state not in offered_or_sold_states
        ):
            return other.queue_position

    return queue_position


def _clamp_queue_position_and_shift_gaps(
    *,
    reservation,
    queue_position,
) -> int:
    """Normalize queue_position and shift other reservations to create space."""
    if isinstance(queue_position, str):
        queue_position = int((queue_position or "").lstrip("0") or "0")
    queue_position = max(1, queue_position)

    active_qs = ApartmentReservation.objects.active().filter(
        apartment_uuid=reservation.apartment_uuid
    )
    if reservation.pk:
        active_qs = active_qs.exclude(pk=reservation.pk)

    current_queue_length = active_qs.count()
    if queue_position > current_queue_length + 1:
        queue_position = current_queue_length + 1

    if (
        reservation.queue_position is None
        or reservation.queue_position != queue_position
    ):
        reservations_qs = ApartmentReservation.objects.filter(
            apartment_uuid=reservation.apartment_uuid
        ).exclude(pk=reservation.pk)

        if reservation.queue_position is not None:
            _adjust_positions(
                reservations_qs,
                "queue_position",
                reservation.queue_position,
                by=-1,
            )

        _adjust_positions(
            reservations_qs,
            "queue_position",
            queue_position,
            by=1,
        )

    return queue_position


def _apply_manual_change_comments(
    *,
    validated_data,
    queue_position: Optional[int],
    new_state,
    old_queue_position,
    submitted_late_changed: bool,
    old_submitted_late,
    new_submitted_late,
) -> None:
    manual_change_comments = []
    # These comments are persisted (not just returned to the client), so keep
    # them stable and Finnish regardless of request Accept-Language.
    with translation.override("fi"):
        if (
            queue_position is not None
            and new_state != ApartmentReservationState.CANCELED
            and old_queue_position != queue_position
        ):
            manual_change_comments.append(
                _("Queue position changed from %(old)s to %(new)s")
                % {"old": old_queue_position, "new": queue_position}
            )
        if submitted_late_changed:
            manual_change_comments.append(
                _("Set to an after-application")
                if new_submitted_late
                else _("Set to sent within application time")
            )
    if not manual_change_comments:
        return

    current_comment = (validated_data.get("comment") or "").strip()
    auto_comment = "; ".join(manual_change_comments)
    validated_data["comment"] = (
        f"{current_comment}; {auto_comment}" if current_comment else auto_comment
    )


class ApartmentReservationViewSet(
    mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = ApartmentReservation.objects.select_related("offer").prefetch_related(
        "apartment_installments", "apartment_installments__payments"
    )
    serializer_class = RootApartmentReservationSerializer

    @staticmethod
    def _normalize_message_item(*, raw_item, drupal_application_id, fallback_body):
        """Normalize Drupal message item to stable API shape for frontend."""
        if not isinstance(raw_item, dict):
            raw_item = {}

        normalized_item = dict(raw_item)
        if not normalized_item.get("application_id"):
            normalized_item["application_id"] = drupal_application_id
        if not normalized_item.get("body"):
            normalized_item["body"] = (
                raw_item.get("message") or raw_item.get("text") or fallback_body
            )
        if normalized_item.get("body") is None:
            normalized_item["body"] = ""
        if not normalized_item.get("created"):
            normalized_item["created"] = int(timezone.now().timestamp())

        created_at = raw_item.get("created_at") or raw_item.get("createdAt")
        if not created_at:
            created_at = datetime.fromtimestamp(
                int(normalized_item["created"]),
                tz=datetime_timezone.utc,
            ).isoformat()
        normalized_item["created_at"] = created_at

        return normalized_item

    @staticmethod
    def _empty_message_thread_response(application_id):
        """Return an empty message thread payload for legacy/non-linked cases."""
        return Response(
            ReservationMessageThreadSerializer(
                {"application_id": application_id, "count": 0, "items": []}
            ).data,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_co_applicant_email(application):
        """Return secondary profile email if known for outgoing sales messages."""
        customer = getattr(application, "customer", None)
        secondary_profile = getattr(customer, "secondary_profile", None)
        email = getattr(secondary_profile, "email", None)
        if not isinstance(email, str):
            return None

        normalized_email = email.strip()
        return normalized_email or None

    def _resolve_message_application(self, request, reservation):
        """Resolve linked application and Drupal id for reservation messages."""
        application_apartment = reservation.application_apartment
        if not application_apartment:
            if request.method.upper() == "GET":
                _logger.info(
                    "messages GET: no linked application for reservation_id=%s "
                    "- returning empty thread",
                    reservation.id,
                )
                return None, None, self._empty_message_thread_response(None)
            raise ValidationError("Reservation has no linked application.")

        application = application_apartment.application
        drupal_application_id = application.drupal_application_id
        if drupal_application_id is not None:
            return application, drupal_application_id, None

        if request.method.upper() == "GET":
            _logger.info(
                "messages GET: drupal_application_id not set for reservation_id=%s "
                "application_id=%s - returning empty thread",
                reservation.id,
                application.id,
            )
            return (
                application,
                drupal_application_id,
                self._empty_message_thread_response(application.id),
            )

        _logger.warning(
            "messages POST: drupal_application_id not set for reservation_id=%s "
            "application_id=%s - messaging unavailable",
            reservation.id,
            application.id,
        )
        return (
            application,
            drupal_application_id,
            Response(
                {"detail": "Messaging unavailable: application has no Drupal ID."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            ),
        )

    def _get_messages_thread_response(self, request, reservation, application_id):
        """Fetch Drupal thread for GET and normalize response payload."""
        client = DrupalMessagingClient()
        unread_count, unread_total = self._mark_read_and_fetch_unread_badge(
            client,
            reservation_id=reservation.id,
            application_id=application_id,
        )

        try:
            thread_payload = client.get_thread(application_id)
        except DrupalMessagingClientError as exc:
            if exc.status_code == 404 or exc.code == "not_found":
                _logger.info(
                    "messages GET: no Drupal thread for reservation_id=%s "
                    "application_id=%s - returning empty thread",
                    reservation.id,
                    application_id,
                )
                return self._empty_message_thread_response(application_id)
            return self._handle_drupal_messaging_error(exc, application_id)

        normalized_items = [
            self._normalize_message_item(
                raw_item=item,
                drupal_application_id=application_id,
                fallback_body="",
            )
            for item in thread_payload.get("items", [])
        ]

        sorted_items = sorted(
            normalized_items,
            key=lambda item: item.get("created", 0),
        )
        response_payload = {
            "application_id": thread_payload.get("application_id", application_id),
            "count": thread_payload.get("count", len(sorted_items)),
            "items": sorted_items,
        }
        if unread_count is not None:
            response_payload["unread_count"] = unread_count
        if unread_total is not None:
            response_payload["unread_total"] = unread_total

        _logger.info(
            "Fetched message thread from Drupal for reservation_id=%s "
            "application_id=%s user_id=%s item_count=%s",
            reservation.id,
            application_id,
            getattr(request.user, "id", None),
            len(sorted_items),
        )
        return Response(
            ReservationMessageThreadSerializer(response_payload).data,
            status=status.HTTP_200_OK,
        )

    def _mark_read_and_fetch_unread_badge(
        self,
        client,
        *,
        reservation_id: int,
        application_id: int,
    ):
        """Mark thread read and fetch updated unread badge counters."""
        try:
            client.post_mark_read(
                viewer_role="sales",
                application_id=application_id,
            )
        except DrupalMessagingClientError as exc:
            self._log_mark_read_error(
                exc,
                reservation_id=reservation_id,
                application_id=application_id,
            )
            return None, None

        try:
            unread_payload = client.get_unread_counts(
                viewer_role="sales",
                application_ids=[application_id],
            )
        except DrupalMessagingClientError as exc:
            self._log_unread_refetch_error(
                exc,
                reservation_id=reservation_id,
                application_id=application_id,
            )
            return None, None

        counts_payload = unread_payload.get("counts", {})
        unread_count = int(counts_payload.get(str(application_id), 0))
        unread_total = int(unread_payload.get("total", unread_count))
        return unread_count, unread_total

    def _log_mark_read_error(
        self,
        exc: DrupalMessagingClientError,
        *,
        reservation_id: int,
        application_id: int,
    ) -> None:
        """Log mark-read integration errors without breaking message thread."""
        if exc.status_code in {401, 403} or exc.code == "forbidden":
            _logger.warning(
                "messages GET mark-read forbidden for reservation_id=%s "
                "application_id=%s status=%s code=%s message=%s",
                reservation_id,
                application_id,
                exc.status_code,
                exc.code,
                exc.message,
            )
            return

        if exc.code == "temporary_failure" or exc.status_code >= 500:
            _logger.warning(
                "messages GET mark-read temporary failure for reservation_id=%s "
                "application_id=%s status=%s code=%s",
                reservation_id,
                application_id,
                exc.status_code,
                exc.code,
            )
            return

        _logger.warning(
            "messages GET mark-read failed for reservation_id=%s "
            "application_id=%s status=%s code=%s",
            reservation_id,
            application_id,
            exc.status_code,
            exc.code,
        )

    def _log_unread_refetch_error(
        self,
        exc: DrupalMessagingClientError,
        *,
        reservation_id: int,
        application_id: int,
    ) -> None:
        """Log unread refetch errors without breaking message thread."""
        if exc.status_code in {401, 403} or exc.code == "forbidden":
            _logger.warning(
                "messages GET unread refetch forbidden for reservation_id=%s "
                "application_id=%s status=%s code=%s message=%s",
                reservation_id,
                application_id,
                exc.status_code,
                exc.code,
                exc.message,
            )
            return

        if exc.code == "temporary_failure" or exc.status_code >= 500:
            _logger.warning(
                "messages GET unread refetch temporary failure for "
                "reservation_id=%s application_id=%s status=%s code=%s",
                reservation_id,
                application_id,
                exc.status_code,
                exc.code,
            )
            return

        _logger.warning(
            "messages GET unread refetch failed for reservation_id=%s "
            "application_id=%s status=%s code=%s",
            reservation_id,
            application_id,
            exc.status_code,
            exc.code,
        )

    @extend_schema(
        responses=ReservationMessageThreadSerializer,
    )
    @action(methods=["GET", "POST"], detail=True)
    def messages(self, request, pk=None):
        reservation = self.get_object()
        _, drupal_application_id, early_response = self._resolve_message_application(
            request,
            reservation,
        )
        if early_response is not None:
            return early_response

        if request.method.upper() == "GET":
            return self._get_messages_thread_response(
                request,
                reservation,
                drupal_application_id,
            )

        client = DrupalMessagingClient()

        serializer = ReservationMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        co_applicant_email = self._get_co_applicant_email(
            reservation.application_apartment.application
        )

        try:
            created_payload = client.post_sales_reply(
                application_id=drupal_application_id,
                body=serializer.validated_data["body"],
                co_applicant_email=co_applicant_email,
            )
        except DrupalMessagingClientError as exc:
            return self._handle_drupal_messaging_error(exc, drupal_application_id)

        _logger.info(
            "Posted sales message to Drupal for reservation_id=%s application_id=%s user_id=%s",  # noqa: E501
            reservation.id,
            drupal_application_id,
            getattr(request.user, "id", None),
        )

        raw_item = (
            created_payload.get("item", {}) if isinstance(created_payload, dict) else {}
        )
        normalized_item = self._normalize_message_item(
            raw_item=raw_item,
            drupal_application_id=drupal_application_id,
            fallback_body=serializer.validated_data["body"],
        )

        return Response(
            ReservationMessageSerializer(normalized_item).data,
            status=status.HTTP_201_CREATED,
        )

    def _handle_drupal_messaging_error(self, exc, application_id):
        if exc.code == "empty_body" or exc.status_code == 400:
            if exc.code == "empty_body":
                return Response(
                    {"body": ["Message body cannot be empty."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": "Bad request to Drupal messaging API."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if exc.status_code == 404 or exc.code == "not_found":
            return Response(
                {"detail": "Application not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if exc.status_code in {401, 403} or exc.code == "forbidden":
            return Response(
                {"detail": "Insufficient permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if exc.code == "temporary_failure" or exc.status_code >= 500:
            _logger.warning(
                "Temporary Drupal messaging error for application_id=%s"
                " status=%s code=%s",
                application_id,
                exc.status_code,
                exc.code,
            )
            return Response(
                {"detail": "Messaging service temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        _logger.error(
            "Unhandled Drupal messaging error for application_id=%s status=%s code=%s",
            application_id,
            exc.status_code,
            exc.code,
        )
        return Response(
            {"detail": "Drupal messaging integration error."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    @extend_schema(
        description="Create either a Hitas contract or a HASO contract PDF based on "
        "the reservation's project's ownership type.",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(methods=["GET"], detail=True)
    def contract(self, request, pk=None):
        reservation = self.get_object()

        data = request.query_params

        sales_price_paid_place = data.get("sales_price_paid_place")
        sales_price_paid_time = data.get("sales_price_paid_time")
        salesperson_uuid = data.get("salesperson_uuid")

        apartment = get_apartment(
            reservation.apartment_uuid, include_project_fields=True
        )
        title = (
            (apartment.title or "").strip().lower().replace(" ", "_").replace(",", "")
        )

        salesperson = None
        try:
            if salesperson_uuid:
                salesperson = get_user_model().objects.get(uuid=salesperson_uuid)
        except get_user_model().DoesNotExist:
            raise ValueError(f"Unknown salesperson: {salesperson_uuid}")

        ownership_type = apartment.project_ownership_type.lower()
        if ownership_type == "hitas":
            filename = f"hitas_sopimus_{title}" if title else "hitas_sopimus"

            pdf_data = create_hitas_contract_pdf(
                reservation,
                sales_price_paid_place,
                sales_price_paid_time,
                salesperson,
            )
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
        old_queue_position = reservation.queue_position
        old_submitted_late = reservation.submitted_late

        data = {"reservation_id": pk}
        data.update(request.data)
        state_change_event_serializer = ApartmentReservationStateChangeEventSerializer(
            data=data
        )
        state_change_event_serializer.is_valid(raise_exception=True)

        validated_data = dict(state_change_event_serializer.validated_data)
        new_submitted_late = validated_data.pop("submitted_late", None)
        queue_position = validated_data.get("queue_position", None)
        if (
            queue_position is None
            and reservation.queue_position_before_cancelation is not None
        ):
            queue_position = reservation.queue_position_before_cancelation

        new_state = validated_data.get("state")
        submitted_late_changed = (
            new_submitted_late is not None
            and old_submitted_late is not None
            and new_submitted_late != old_submitted_late
        )

        if submitted_late_changed:
            reservation.submitted_late = new_submitted_late
            reservation.save(update_fields=["submitted_late"])
            if queue_position is None:
                queue_position = (
                    _recalculate_queue_position_for_haso_on_submitted_late_change(
                        reservation=reservation,
                        new_state=new_state,
                    )
                )

        if (
            queue_position is not None
            and new_state != ApartmentReservationState.CANCELED
        ):
            queue_position = _clamp_queue_position_and_shift_gaps(
                reservation=reservation,
                queue_position=queue_position,
            )

        _apply_manual_change_comments(
            validated_data=validated_data,
            queue_position=queue_position,
            new_state=new_state,
            old_queue_position=old_queue_position,
            submitted_late_changed=submitted_late_changed,
            old_submitted_late=old_submitted_late,
            new_submitted_late=new_submitted_late,
        )

        validated_data["queue_position"] = queue_position
        state_change_event = reservation.set_state(
            **validated_data,
            user=request.user,
        )

        if (
            queue_position is not None
            and new_state != ApartmentReservationState.CANCELED
        ):
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
