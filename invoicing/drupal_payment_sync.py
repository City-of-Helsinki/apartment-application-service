import logging
import time
from threading import Thread
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apartment.elastic.queries import get_apartment
from invoicing.models import DrupalPaymentSyncOutboxEvent

logger = logging.getLogger(__name__)


DEFAULT_DRUPAL_PAYMENTS_SYNC_PATH = "/api/asu/application-payments/sync"
DEFAULT_DRUPAL_PAYMENTS_SYNC_MAX_ATTEMPTS = 3
DEFAULT_DRUPAL_PAYMENTS_SYNC_BACKOFF_BASE_SECONDS = 30
DEFAULT_DRUPAL_PAYMENTS_SYNC_BACKOFF_MAX_SECONDS = 1800
DRUPAL_PAYMENTS_SYNC_TOKEN_CACHE_KEY = "drupal_payment_sync:oauth_access_token:v1"


class DrupalPaymentSyncError(Exception):
    """Base exception for Drupal payment sync failures."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DrupalPaymentSyncRetryableError(DrupalPaymentSyncError):
    """Signals a retryable upstream failure."""


class DrupalPaymentSyncNonRetryableError(DrupalPaymentSyncError):
    """Signals a non-retryable upstream failure."""


def _sync_base_url() -> str:
    """Return Drupal payments sync base URL from existing project settings."""
    return getattr(
        settings,
        "DRUPAL_PAYMENTS_SYNC_BASE_URL",
        settings.DRUPAL_SEARCH_API_BASE_URL,
    )


def _sync_path() -> str:
    """Return Drupal payments sync relative path."""
    return getattr(
        settings,
        "DRUPAL_PAYMENTS_SYNC_PATH",
        DEFAULT_DRUPAL_PAYMENTS_SYNC_PATH,
    )


def _sync_timeout() -> int:
    """Return request timeout for Drupal payments sync."""
    return int(
        getattr(
            settings,
            "DRUPAL_PAYMENTS_SYNC_TIMEOUT",
            settings.DRUPAL_SEARCH_API_TIMEOUT,
        )
    )


def _sync_verify_ssl() -> bool:
    """Return SSL verification flag for Drupal payments sync."""
    return bool(
        getattr(
            settings,
            "DRUPAL_PAYMENTS_SYNC_VERIFY_SSL",
            settings.DRUPAL_SEARCH_API_VERIFY_SSL,
        )
    )


def _sync_max_attempts() -> int:
    """Return max send attempts for outbox dispatch."""
    default_attempts = max(
        int(getattr(settings, "DRUPAL_SEARCH_API_RETRY_COUNT", 2)) + 1,
        DEFAULT_DRUPAL_PAYMENTS_SYNC_MAX_ATTEMPTS,
    )
    return max(
        int(
            getattr(
                settings,
                "DRUPAL_PAYMENTS_SYNC_MAX_ATTEMPTS",
                default_attempts,
            )
        ),
        1,
    )


def _sync_backoff_base_seconds() -> int:
    """Return base delay for exponential retry backoff."""
    return max(
        int(
            getattr(
                settings,
                "DRUPAL_PAYMENTS_SYNC_BACKOFF_BASE_SECONDS",
                DEFAULT_DRUPAL_PAYMENTS_SYNC_BACKOFF_BASE_SECONDS,
            )
        ),
        1,
    )


def _sync_backoff_max_seconds() -> int:
    """Return max delay cap for exponential retry backoff."""
    return max(
        int(
            getattr(
                settings,
                "DRUPAL_PAYMENTS_SYNC_BACKOFF_MAX_SECONDS",
                DEFAULT_DRUPAL_PAYMENTS_SYNC_BACKOFF_MAX_SECONDS,
            )
        ),
        _sync_backoff_base_seconds(),
    )


def _extract_value(data: Any, key: str) -> Any:
    """Extract value from dict-like or object-like source."""
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)


def _build_safe_url(base_url: str, path: str) -> str:
    """Build a URL safely from configured base URL and relative path."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string.")

    candidate = path.strip()
    if "://" in candidate or candidate.startswith("//"):
        raise ValueError("Absolute URLs are not allowed.")

    segments = [segment for segment in candidate.split("/") if segment != ""]
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("Path traversal segments are not allowed.")

    base = base_url.rstrip("/") + "/"
    full = urljoin(base, "/".join(segments))

    base_parsed = urlparse(base)
    full_parsed = urlparse(full)
    if (base_parsed.scheme, base_parsed.netloc) != (
        full_parsed.scheme,
        full_parsed.netloc,
    ):
        raise ValueError("Resolved URL escaped configured base URL.")

    return full


def build_drupal_payment_idempotency_key(
    *,
    application_id: int,
    reservation_id: int,
    installment_type: str,
    reference_number: str,
) -> str:
    """Build deterministic idempotency key for a Drupal payment sync row."""
    return (
        f"{application_id}:{reservation_id}:{installment_type}:{reference_number}"
    )


def _format_amount(amount: Decimal) -> str:
    """Format amount to fixed two-decimal euro string."""
    normalized_amount = Decimal(str(amount))
    return f"{normalized_amount.quantize(Decimal('0.01'))}"


def _build_payment_payload(
    *,
    application_id: int,
    reservation_id: int,
    project_uuid: str,
    installment_type: str,
    amount: Decimal,
    due_date,
    account_number: str,
    reference_number: str,
    sent_to_sap_at: datetime,
    source_event_id,
) -> Dict[str, Any]:
    """Build Drupal payment payload from reservation installment fields."""
    return {
        "application_id": application_id,
        "reservation_id": str(reservation_id),
        "project_uuid": str(project_uuid),
        "installment_type": installment_type,
        "amount": _format_amount(amount),
        "due_date": due_date.isoformat() if due_date else None,
        "account_number": account_number,
        "reference_number": reference_number,
        "sent_to_sap_at": sent_to_sap_at.isoformat(),
        "source_event_id": str(source_event_id),
        "sent_to_sap": True,
    }


def _get_drupal_application_id(installment) -> int:
    """Resolve Drupal application id from installment reservation relation."""
    reservation = installment.apartment_reservation
    application_apartment = reservation.application_apartment
    if not application_apartment or not application_apartment.application:
        raise ValidationError(
            "Apartment reservation is not linked to an application apartment."
        )

    drupal_application_id = application_apartment.application.drupal_application_id
    if drupal_application_id is None:
        raise ValidationError(
            "Drupal application id is missing for the reservation application."
        )

    return drupal_application_id


def _get_project_uuid(installment) -> str:
    """Resolve project UUID for installment reservation apartment."""
    apartment_data = get_apartment(
        installment.apartment_reservation.apartment_uuid,
        include_project_fields=True,
    )
    project_uuid = _extract_value(apartment_data, "project_uuid")
    if not project_uuid:
        raise ValidationError("Project UUID is missing for reservation apartment.")
    return str(project_uuid)


def create_drupal_payment_sync_outbox_event(
    installment,
    sent_to_sap_at: datetime,
) -> DrupalPaymentSyncOutboxEvent:
    """Create idempotent outbox event for Drupal payment sync."""
    application_id = _get_drupal_application_id(installment)
    project_uuid = _get_project_uuid(installment)
    source_event_id = uuid4()
    idempotency_key = build_drupal_payment_idempotency_key(
        application_id=application_id,
        reservation_id=installment.apartment_reservation_id,
        installment_type=installment.type.value,
        reference_number=installment.reference_number,
    )

    payload = _build_payment_payload(
        application_id=application_id,
        reservation_id=installment.apartment_reservation_id,
        project_uuid=project_uuid,
        installment_type=installment.type.value,
        amount=installment.value,
        due_date=installment.due_date,
        account_number=installment.account_number,
        reference_number=installment.reference_number,
        sent_to_sap_at=sent_to_sap_at,
        source_event_id=source_event_id,
    )

    event, _ = DrupalPaymentSyncOutboxEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "apartment_installment": installment,
            "application_id": application_id,
            "reservation_id": installment.apartment_reservation_id,
            "project_uuid": project_uuid,
            "installment_type": installment.type.value,
            "amount": installment.value,
            "due_date": installment.due_date,
            "account_number": installment.account_number,
            "reference_number": installment.reference_number,
            "sent_to_sap_at": sent_to_sap_at,
            "source_event_id": source_event_id,
            "payload": payload,
            "next_retry_at": timezone.now(),
        },
    )

    return event


def _build_headers(correlation_id: str) -> Dict[str, str]:
    """Build headers for Drupal payment sync request."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Correlation-Id": correlation_id,
    }
    token = _get_sync_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_sync_auth_token() -> str:
    """Resolve auth token using existing Drupal integration scheme."""
    explicit_token = getattr(settings, "DRUPAL_PAYMENTS_SYNC_AUTH_TOKEN", "")
    if explicit_token:
        return explicit_token

    oauth_token = _get_oauth_access_token()
    if oauth_token:
        return oauth_token

    return getattr(settings, "DRUPAL_SERVER_AUTH_TOKEN", "")


def _get_oauth_access_token() -> str:
    """Fetch and cache OAuth token from Drupal token endpoint."""
    token_url = getattr(settings, "DRUPAL_SEARCH_API_TOKEN_URL", "")
    client_id = getattr(settings, "DRUPAL_SEARCH_API_CLIENT_ID", "")
    client_secret = getattr(settings, "DRUPAL_SEARCH_API_CLIENT_SECRET", "")

    if not token_url or not client_id or not client_secret:
        return ""

    now = time.time()
    cached = cache.get(DRUPAL_PAYMENTS_SYNC_TOKEN_CACHE_KEY)
    if isinstance(cached, dict):
        token = cached.get("token", "")
        expires_at = float(cached.get("expires_at", 0))
        if token and now < expires_at:
            return token

    try:
        response = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "rest_client",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_sync_timeout(),
            verify=_sync_verify_ssl(),
        )
    except requests.RequestException:
        return ""

    if response.status_code >= 400:
        return ""

    payload = response.json()
    token = str(payload.get("access_token", ""))
    if not token:
        return ""

    expires_in = int(payload.get("expires_in", 3600))
    expires_at = now + max(expires_in - 30, 1)
    cache.set(
        DRUPAL_PAYMENTS_SYNC_TOKEN_CACHE_KEY,
        {"token": token, "expires_at": expires_at},
        timeout=max(expires_in - 30, 1),
    )
    return token


def _post_event_to_drupal(event: DrupalPaymentSyncOutboxEvent, correlation_id: str) -> None:
    """Send a single outbox payment event to Drupal endpoint."""
    url = _build_safe_url(
        _sync_base_url(),
        _sync_path(),
    )

    try:
        response = requests.post(
            url,
            json={"payments": [event.payload]},
            headers=_build_headers(correlation_id),
            timeout=_sync_timeout(),
            verify=_sync_verify_ssl(),
        )
    except requests.RequestException as exc:
        raise DrupalPaymentSyncRetryableError(
            "Drupal payment sync failed due to a network error."
        ) from exc

    if response.status_code == 200:
        return

    if 500 <= response.status_code:
        raise DrupalPaymentSyncRetryableError(
            "Drupal payment sync temporary upstream failure.",
            status_code=response.status_code,
        )

    raise DrupalPaymentSyncNonRetryableError(
        "Drupal payment sync rejected payload.",
        status_code=response.status_code,
    )


def _get_retry_delay_seconds(attempt_number: int) -> int:
    """Calculate bounded exponential backoff delay for next retry."""
    base = _sync_backoff_base_seconds()
    max_delay = _sync_backoff_max_seconds()
    return min(base * (2 ** max(attempt_number - 1, 0)), max_delay)


def _mark_retryable_failure(
    event: DrupalPaymentSyncOutboxEvent,
    exc: DrupalPaymentSyncRetryableError,
) -> None:
    """Update outbox state for retryable failures."""
    max_attempts = _sync_max_attempts()
    next_attempt_count = event.attempts + 1

    event.attempts = next_attempt_count
    event.last_error_code = str(exc.status_code or "network_error")
    event.last_error_message = str(exc)

    if next_attempt_count >= max_attempts:
        event.status = DrupalPaymentSyncOutboxEvent.Status.DEAD_LETTER
        event.processed_at = timezone.now()
    else:
        event.status = DrupalPaymentSyncOutboxEvent.Status.FAILED
        delay_seconds = _get_retry_delay_seconds(next_attempt_count)
        event.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)

    event.save(
        update_fields=[
            "attempts",
            "status",
            "last_error_code",
            "last_error_message",
            "next_retry_at",
            "processed_at",
            "updated_at",
        ]
    )


def _mark_non_retryable_failure(
    event: DrupalPaymentSyncOutboxEvent,
    exc: DrupalPaymentSyncNonRetryableError,
) -> None:
    """Update outbox state for non-retryable failures."""
    event.attempts = event.attempts + 1
    event.status = DrupalPaymentSyncOutboxEvent.Status.DEAD_LETTER
    event.last_error_code = str(exc.status_code or "validation_error")
    event.last_error_message = str(exc)
    event.processed_at = timezone.now()
    event.save(
        update_fields=[
            "attempts",
            "status",
            "last_error_code",
            "last_error_message",
            "processed_at",
            "updated_at",
        ]
    )


def dispatch_drupal_payment_sync_events(batch_size: int = 100) -> int:
    """Dispatch pending/failed outbox events to Drupal with retries."""
    now = timezone.now()
    eligible_ids = list(
        DrupalPaymentSyncOutboxEvent.objects.filter(
            status__in=(
                DrupalPaymentSyncOutboxEvent.Status.PENDING,
                DrupalPaymentSyncOutboxEvent.Status.FAILED,
            ),
            next_retry_at__lte=now,
        )
        .order_by("next_retry_at", "id")
        .values_list("id", flat=True)[:batch_size]
    )

    processed = 0
    for event_id in eligible_ids:
        with transaction.atomic():
            event = (
                DrupalPaymentSyncOutboxEvent.objects.select_for_update()
                .select_related("apartment_installment")
                .get(id=event_id)
            )

            if event.status not in (
                DrupalPaymentSyncOutboxEvent.Status.PENDING,
                DrupalPaymentSyncOutboxEvent.Status.FAILED,
            ):
                continue

            correlation_id = str(uuid4())

            try:
                _post_event_to_drupal(event, correlation_id)
            except DrupalPaymentSyncRetryableError as exc:
                _mark_retryable_failure(event, exc)
                logger.warning(
                    "drupal_payment_sync_retryable_failure",
                    extra={
                        "event_id": event.id,
                        "source_event_id": str(event.source_event_id),
                        "idempotency_key": event.idempotency_key,
                        "correlation_id": correlation_id,
                        "status_code": exc.status_code,
                        "attempts": event.attempts,
                    },
                )
            except DrupalPaymentSyncNonRetryableError as exc:
                _mark_non_retryable_failure(event, exc)
                logger.error(
                    "drupal_payment_sync_non_retryable_failure",
                    extra={
                        "event_id": event.id,
                        "source_event_id": str(event.source_event_id),
                        "idempotency_key": event.idempotency_key,
                        "correlation_id": correlation_id,
                        "status_code": exc.status_code,
                        "attempts": event.attempts,
                    },
                )
            else:
                event.status = DrupalPaymentSyncOutboxEvent.Status.SENT
                event.attempts = event.attempts + 1
                event.processed_at = timezone.now()
                event.last_error_code = ""
                event.last_error_message = ""
                event.save(
                    update_fields=[
                        "status",
                        "attempts",
                        "processed_at",
                        "last_error_code",
                        "last_error_message",
                        "updated_at",
                    ]
                )
                logger.info(
                    "drupal_payment_sync_success",
                    extra={
                        "event_id": event.id,
                        "source_event_id": str(event.source_event_id),
                        "idempotency_key": event.idempotency_key,
                        "correlation_id": correlation_id,
                        "attempts": event.attempts,
                    },
                )

            processed += 1

    queue_size = DrupalPaymentSyncOutboxEvent.objects.filter(
        status__in=(
            DrupalPaymentSyncOutboxEvent.Status.PENDING,
            DrupalPaymentSyncOutboxEvent.Status.FAILED,
        )
    ).count()
    logger.info(
        "drupal_payment_sync_metrics",
        extra={
            "processed_count": processed,
            "queue_size": queue_size,
        },
    )
    return processed


def trigger_drupal_payment_sync_background_dispatch() -> None:
    """Run outbox dispatch in a daemon thread without blocking request flow."""
    thread = Thread(
        target=_run_background_dispatch,
        daemon=True,
    )
    thread.start()


def _run_background_dispatch() -> None:
    """Execute a single best-effort dispatch pass and swallow failures."""
    try:
        dispatch_drupal_payment_sync_events(batch_size=100)
    except Exception:
        logger.exception("drupal_payment_sync_background_dispatch_failed")


def resend_failed_drupal_payment_sync_events(limit: Optional[int] = None) -> int:
    """Reset failed outbox events back to pending for manual resend."""
    failed_events = DrupalPaymentSyncOutboxEvent.objects.filter(
        status=DrupalPaymentSyncOutboxEvent.Status.FAILED
    ).order_by("id")
    if limit:
        failed_ids = list(failed_events.values_list("id", flat=True)[:limit])
        failed_events = DrupalPaymentSyncOutboxEvent.objects.filter(id__in=failed_ids)

    updated_count = failed_events.update(
        status=DrupalPaymentSyncOutboxEvent.Status.PENDING,
        next_retry_at=timezone.now(),
        last_error_code="",
        last_error_message="",
    )
    return updated_count
