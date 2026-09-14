from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
import requests
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory
from invoicing.drupal_payment_sync import (
    build_drupal_payment_idempotency_key,
    create_drupal_payment_sync_outbox_event,
    dispatch_drupal_payment_sync_events,
)
from invoicing.models import DrupalPaymentSyncOutboxEvent
from invoicing.tests.factories import ApartmentInstallmentFactory


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def drupal_payment_sync_settings(settings):
    settings.DRUPAL_PAYMENTS_SYNC_BASE_URL = "https://drupal.example"
    settings.DRUPAL_PAYMENTS_SYNC_PATH = "/api/asu/application-payments/sync"
    settings.DRUPAL_PAYMENTS_SYNC_TIMEOUT = 3
    settings.DRUPAL_PAYMENTS_SYNC_VERIFY_SSL = True
    settings.DRUPAL_PAYMENTS_SYNC_MAX_ATTEMPTS = 3
    settings.DRUPAL_PAYMENTS_SYNC_BACKOFF_BASE_SECONDS = 10
    settings.DRUPAL_PAYMENTS_SYNC_BACKOFF_MAX_SECONDS = 120


@pytest.mark.django_db
def test_dispatch_uses_existing_drupal_search_settings_when_custom_missing(
    monkeypatch,
    settings,
):
    """Dispatch should work without custom DRUPAL_PAYMENTS_SYNC settings.

    - Uses DRUPAL_SEARCH_API_* defaults for URL/timeout/SSL.
    - Sends to the default Drupal payments sync path.
    """
    settings.DRUPAL_SEARCH_API_BASE_URL = "https://drupal.example"
    settings.DRUPAL_SEARCH_API_TIMEOUT = 7
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = False

    for name in (
        "DRUPAL_PAYMENTS_SYNC_BASE_URL",
        "DRUPAL_PAYMENTS_SYNC_PATH",
        "DRUPAL_PAYMENTS_SYNC_TIMEOUT",
        "DRUPAL_PAYMENTS_SYNC_VERIFY_SSL",
        "DRUPAL_PAYMENTS_SYNC_MAX_ATTEMPTS",
        "DRUPAL_PAYMENTS_SYNC_BACKOFF_BASE_SECONDS",
        "DRUPAL_PAYMENTS_SYNC_BACKOFF_MAX_SECONDS",
    ):
        if hasattr(settings, name):
            delattr(settings, name)

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=777,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    create_drupal_payment_sync_outbox_event(installment, timezone.now())

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None, verify=None, data=None):
        if "oauth/token" in url:
            return _FakeResponse(
                status_code=200,
                payload={"access_token": "oauth-token", "expires_in": 3600},
            )
        captured["url"] = url
        captured["timeout"] = timeout
        captured["verify"] = verify
        return _FakeResponse(status_code=200, payload={"success": True})

    monkeypatch.setattr(requests, "post", fake_post)

    processed = dispatch_drupal_payment_sync_events(batch_size=10)

    assert processed == 1
    assert captured["url"] == "https://drupal.example/api/asu/application-payments/sync"
    assert captured["timeout"] == 7
    assert captured["verify"] is False


@pytest.mark.django_db
def test_create_outbox_event_builds_expected_payload(drupal_payment_sync_settings):
    """Create outbox payload from reservation installment data.

    - Uses Drupal application id from reservation application.
    - Includes required payment and linkage fields.
    - Generates source_event_id and idempotency key.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=32145,
    )
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        value=Decimal("32350.00"),
        due_date=timezone.localdate(),
        account_number="FI0212345600000785",
        reference_number="123456789012",
    )
    sent_to_sap_at = timezone.now()

    event = create_drupal_payment_sync_outbox_event(
        installment=installment,
        sent_to_sap_at=sent_to_sap_at,
    )

    assert event.application_id == 32145
    assert event.reservation_id == reservation.id
    assert event.installment_type == installment.type.value
    assert event.reference_number == installment.reference_number
    assert event.source_event_id is not None
    assert event.idempotency_key == build_drupal_payment_idempotency_key(
        application_id=32145,
        reservation_id=reservation.id,
        installment_type=installment.type.value,
        reference_number=installment.reference_number,
    )
    assert event.payload == {
        "application_id": 32145,
        "reservation_id": str(reservation.id),
        "project_uuid": str(apartment.project_uuid),
        "installment_type": installment.type.value,
        "amount": "32350.00",
        "due_date": timezone.localdate().isoformat(),
        "account_number": "FI0212345600000785",
        "reference_number": "123456789012",
        "sent_to_sap_at": sent_to_sap_at.isoformat(),
        "source_event_id": str(event.source_event_id),
        "sent_to_sap": True,
    }


@pytest.mark.django_db
def test_create_outbox_event_is_idempotent(drupal_payment_sync_settings):
    """Repeated creation for same installment must not duplicate rows.

    - First creation writes one outbox row.
    - Second creation returns existing row by idempotency key.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=10,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    sent_to_sap_at = timezone.now()

    first = create_drupal_payment_sync_outbox_event(installment, sent_to_sap_at)
    second = create_drupal_payment_sync_outbox_event(installment, sent_to_sap_at)

    assert first.id == second.id
    assert DrupalPaymentSyncOutboxEvent.objects.count() == 1


@pytest.mark.django_db
def test_dispatch_success_marks_event_sent(
    drupal_payment_sync_settings,
    monkeypatch,
):
    """Successful Drupal sync updates outbox status.

    - Dispatcher posts expected wrapper payload.
    - Event is marked sent and attempts increment.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=55,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    event = create_drupal_payment_sync_outbox_event(installment, timezone.now())

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None, verify=None, data=None):
        if "oauth/token" in url:
            return _FakeResponse(
                status_code=200,
                payload={"access_token": "oauth-token", "expires_in": 3600},
            )
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(status_code=200, payload={"success": True})

    monkeypatch.setattr(requests, "post", fake_post)

    processed = dispatch_drupal_payment_sync_events(batch_size=10)

    event.refresh_from_db()
    assert processed == 1
    assert event.status == DrupalPaymentSyncOutboxEvent.Status.SENT
    assert event.attempts == 1
    assert captured["url"] == "https://drupal.example/api/asu/application-payments/sync"
    assert captured["json"] == {"payments": [event.payload]}
    assert "X-Correlation-Id" in captured["headers"]


@pytest.mark.django_db
def test_dispatch_uses_server_token_when_sync_token_missing(
    drupal_payment_sync_settings,
    settings,
    monkeypatch,
):
    """Authorization header falls back to DRUPAL_SERVER_AUTH_TOKEN.

    - Sync token is absent from settings.
    - Dispatcher sends Bearer token from DRUPAL_SERVER_AUTH_TOKEN.
    """
    if hasattr(settings, "DRUPAL_PAYMENTS_SYNC_AUTH_TOKEN"):
        delattr(settings, "DRUPAL_PAYMENTS_SYNC_AUTH_TOKEN")
    settings.DRUPAL_SEARCH_API_TOKEN_URL = ""
    settings.DRUPAL_SEARCH_API_CLIENT_ID = ""
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = ""
    settings.DRUPAL_SERVER_AUTH_TOKEN = "server-token"

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=59,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    create_drupal_payment_sync_outbox_event(installment, timezone.now())

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None, verify=None, data=None):
        captured["headers"] = headers
        return _FakeResponse(status_code=200, payload={"success": True})

    monkeypatch.setattr(requests, "post", fake_post)

    processed = dispatch_drupal_payment_sync_events(batch_size=10)

    assert processed == 1
    assert captured["headers"]["Authorization"] == "Bearer server-token"


@pytest.mark.django_db
def test_dispatch_prefers_oauth_token_over_server_token(
    drupal_payment_sync_settings,
    settings,
    monkeypatch,
):
    """OAuth token is preferred over DRUPAL_SERVER_AUTH_TOKEN fallback.

    - Sync token is absent.
    - OAuth credentials are available.
    - Dispatcher sends OAuth bearer token, not server token.
    """
    if hasattr(settings, "DRUPAL_PAYMENTS_SYNC_AUTH_TOKEN"):
        delattr(settings, "DRUPAL_PAYMENTS_SYNC_AUTH_TOKEN")
    settings.DRUPAL_SEARCH_API_TOKEN_URL = "https://drupal.example/oauth/token"
    settings.DRUPAL_SEARCH_API_CLIENT_ID = "client-id"
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = "client-secret"
    settings.DRUPAL_SERVER_AUTH_TOKEN = "server-token"

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=60,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    create_drupal_payment_sync_outbox_event(installment, timezone.now())

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None, verify=None, data=None):
        if url == settings.DRUPAL_SEARCH_API_TOKEN_URL:
            return _FakeResponse(
                status_code=200,
                payload={"access_token": "oauth-token", "expires_in": 3600},
            )
        captured["headers"] = headers
        return _FakeResponse(status_code=200, payload={"success": True})

    monkeypatch.setattr(requests, "post", fake_post)

    processed = dispatch_drupal_payment_sync_events(batch_size=10)

    assert processed == 1
    assert captured["headers"]["Authorization"] == "Bearer oauth-token"


@pytest.mark.django_db
def test_dispatch_5xx_retries_then_dead_letter(
    drupal_payment_sync_settings,
    monkeypatch,
):
    """Server errors should be retried with bounded attempts.

    - First failure goes to failed state with next retry timestamp.
    - After max attempts event becomes dead letter.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=56,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    event = create_drupal_payment_sync_outbox_event(installment, timezone.now())

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(status_code=500, payload={}),
    )

    for _ in range(3):
        event.next_retry_at = timezone.now() - timedelta(seconds=1)
        event.save(update_fields=["next_retry_at"])
        dispatch_drupal_payment_sync_events(batch_size=10)
        event.refresh_from_db()

    assert event.status == DrupalPaymentSyncOutboxEvent.Status.DEAD_LETTER
    assert event.attempts == 3


@pytest.mark.django_db
def test_dispatch_4xx_is_non_retryable(drupal_payment_sync_settings, monkeypatch):
    """Client errors should not be retried forever.

    - 4xx response marks event as dead letter.
    - Next retry timestamp is not moved into retry loop.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=57,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    event = create_drupal_payment_sync_outbox_event(installment, timezone.now())

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(status_code=400, payload={}),
    )

    dispatch_drupal_payment_sync_events(batch_size=10)

    event.refresh_from_db()
    assert event.status == DrupalPaymentSyncOutboxEvent.Status.DEAD_LETTER
    assert event.attempts == 1


@pytest.mark.django_db
def test_add_to_sap_creates_outbox_atomically_on_failure(
    sales_ui_salesperson_api_client,
):
    """Outbox and add-to-sap flag are persisted atomically.

    - If outbox creation fails, endpoint fails.
    - added_to_be_sent_to_sap_at remains unchanged due to rollback.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        added_to_be_sent_to_sap_at=None,
    )
    ApartmentInstallmentFactory(apartment_reservation=reservation)

    url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation.id},
    )

    with mock.patch(
        "invoicing.api.views.create_drupal_payment_sync_outbox_event",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            sales_ui_salesperson_api_client.post(
                url + f"?types={installment.type.value}",
                format="json",
            )

    installment.refresh_from_db()
    assert installment.added_to_be_sent_to_sap_at is None
    assert DrupalPaymentSyncOutboxEvent.objects.count() == 0


@pytest.mark.django_db
def test_add_to_sap_repeat_does_not_duplicate_outbox(
    sales_ui_salesperson_api_client,
    drupal_payment_sync_settings,
):
    """Repeated Lähetä SAP should not create duplicate payment sync rows.

    - First call creates one outbox event.
    - Second call is rejected as already added and outbox count stays one.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        added_to_be_sent_to_sap_at=None,
    )

    url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation.id},
    )

    first = sales_ui_salesperson_api_client.post(
        url + f"?types={installment.type.value}",
        format="json",
    )
    second = sales_ui_salesperson_api_client.post(
        url + f"?types={installment.type.value}",
        format="json",
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert DrupalPaymentSyncOutboxEvent.objects.count() == 1


@pytest.mark.django_db
def test_add_to_sap_triggers_background_dispatch(
    sales_ui_salesperson_api_client,
    monkeypatch,
):
    """Add-to-SAP should schedule best-effort background Drupal sync.

    - Endpoint returns success for SAP flow.
    - Background trigger is invoked after transaction commit.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        added_to_be_sent_to_sap_at=None,
    )

    url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation.id},
    )

    captured = {"called": 0}

    def fake_trigger():
        captured["called"] += 1

    monkeypatch.setattr(
        "invoicing.api.views.trigger_drupal_payment_sync_background_dispatch",
        fake_trigger,
    )

    response = sales_ui_salesperson_api_client.post(
        url + f"?types={installment.type.value}",
        format="json",
    )

    assert response.status_code == 200
    assert captured["called"] == 1


@pytest.mark.django_db
def test_add_to_sap_ignores_background_dispatch_failures(
    sales_ui_salesperson_api_client,
    monkeypatch,
):
    """Best-effort trigger failures must not fail SAP-facing endpoint.

    - Background trigger raises.
    - Endpoint still responds with success.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        added_to_be_sent_to_sap_at=None,
    )

    url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation.id},
    )

    def failing_trigger():
        raise RuntimeError("dispatch trigger failed")

    monkeypatch.setattr(
        "invoicing.api.views.trigger_drupal_payment_sync_background_dispatch",
        failing_trigger,
    )

    response = sales_ui_salesperson_api_client.post(
        url + f"?types={installment.type.value}",
        format="json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_contract_payload_shape_for_drupal(drupal_payment_sync_settings):
    """Ensure payload contract matches Drupal schema expectations.

    - Wrapper uses top-level payments list in dispatcher payload source.
    - Payment object includes required keys and expected value types.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=97,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    event = create_drupal_payment_sync_outbox_event(installment, timezone.now())

    payload = event.payload

    required_keys = {
        "application_id",
        "reservation_id",
        "project_uuid",
        "installment_type",
        "amount",
        "due_date",
        "account_number",
        "reference_number",
        "sent_to_sap_at",
        "source_event_id",
        "sent_to_sap",
    }
    assert required_keys.issubset(payload.keys())
    assert isinstance(payload["application_id"], int)
    assert isinstance(payload["reservation_id"], str)
    assert isinstance(payload["project_uuid"], str)
    assert isinstance(payload["installment_type"], str)
    assert isinstance(payload["amount"], str)
    assert isinstance(payload["due_date"], str)
    assert isinstance(payload["sent_to_sap"], bool)


@pytest.mark.django_db
def test_resend_failed_command_moves_event_to_pending(
    drupal_payment_sync_settings,
):
    """Manual resend command should reactivate failed events.

    - Dead-letter event remains untouched.
    - Failed event is moved back to pending for worker pickup.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=58,
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    event = create_drupal_payment_sync_outbox_event(installment, timezone.now())
    event.status = DrupalPaymentSyncOutboxEvent.Status.FAILED
    event.next_retry_at = timezone.now() + timedelta(days=1)
    event.save(update_fields=["status", "next_retry_at"])

    call_command("resend_failed_drupal_payments")

    event.refresh_from_db()
    assert event.status == DrupalPaymentSyncOutboxEvent.Status.PENDING
    assert event.next_retry_at <= timezone.now()
