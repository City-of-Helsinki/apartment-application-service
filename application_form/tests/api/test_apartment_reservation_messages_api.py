import pytest
from django.urls import reverse

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory
from users.tests.factories import ProfileFactory


class _FakeMessagingClient:
    def __init__(
        self,
        thread_payload=None,
        post_payload=None,
        inbox_payload=None,
        to_raise=None,
        mark_read_to_raise=None,
        unread_payload=None,
        unread_to_raise=None,
    ):
        self._thread_payload = thread_payload
        self._post_payload = post_payload
        self._inbox_payload = inbox_payload
        self._to_raise = to_raise
        self._mark_read_to_raise = mark_read_to_raise
        self._unread_payload = unread_payload
        self._unread_to_raise = unread_to_raise
        self.get_calls = []
        self.post_calls = []
        self.unread_calls = []
        self.inbox_calls = []
        self.mark_read_calls = []

    def get_thread(self, application_id):
        self.get_calls.append(application_id)
        if self._to_raise:
            raise self._to_raise
        return self._thread_payload

    def post_sales_reply(self, application_id, body, co_applicant_email=None):
        self.post_calls.append((application_id, body, co_applicant_email))
        if self._to_raise:
            raise self._to_raise
        return self._post_payload

    def get_unread_counts(self, *, viewer_role, application_ids=None):
        self.unread_calls.append((viewer_role, application_ids))
        if self._unread_to_raise:
            raise self._unread_to_raise
        if self._to_raise:
            raise self._to_raise
        if self._unread_payload is not None:
            return self._unread_payload
        return self._thread_payload

    def get_inbox_summary(self, *, viewer_role, application_ids=None):
        self.inbox_calls.append((viewer_role, application_ids))
        if self._to_raise:
            raise self._to_raise
        return self._inbox_payload

    def post_mark_read(
        self,
        *,
        viewer_role,
        application_id=None,
        application_ids=None,
    ):
        self.mark_read_calls.append((viewer_role, application_id, application_ids))
        if self._mark_read_to_raise:
            raise self._mark_read_to_raise
        if self._to_raise:
            raise self._to_raise
        return {"status": "ok"}


@pytest.mark.django_db
def test_reservation_messages_get_unauthorized(user_api_client):
    """Only sales users may access reservation messages endpoint.

    - A regular authenticated user receives 403.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    response = user_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_reservation_messages_get_success_sorted(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Thread messages are returned in ascending created order.

    - Upstream may return out-of-order items.
    - Backend normalizes order for frontend.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=777,
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        thread_payload={
            "application_id": drupal_id,
            "count": 2,
            "items": [
                {"id": 2, "body": "second", "created": 1710000100},
                {"id": 1, "body": "first", "created": 1710000000},
            ],
        },
        unread_payload={"counts": {str(drupal_id): 0}, "total": 0},
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["application_id"] == drupal_id
    assert [item["id"] for item in response.data["items"]] == [1, 2]
    assert response.data["unread_count"] == 0
    assert response.data["unread_total"] == 0
    assert fake_client.get_calls == [drupal_id]
    assert fake_client.mark_read_calls == [("sales", drupal_id, None)]
    assert fake_client.unread_calls == [("sales", [drupal_id])]


@pytest.mark.django_db
def test_reservation_messages_get_mark_read_forbidden_does_not_break_page(
    sales_ui_salesperson_api_client, monkeypatch, caplog
):
    """Open chat should survive mark-read 403 and log upstream details."""

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=779,
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        thread_payload={
            "application_id": drupal_id,
            "count": 1,
            "items": [{"id": 1, "body": "first", "created": 1710000000}],
        },
        mark_read_to_raise=DrupalMessagingClientError(
            status_code=403,
            code="forbidden",
            message="Forbidden by policy",
        ),
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    with caplog.at_level("WARNING"):
        response = sales_ui_salesperson_api_client.get(
            reverse(
                "application_form:sales-apartment-reservation-messages",
                kwargs={"pk": reservation.id},
            )
        )

    assert response.status_code == 200
    assert response.data["application_id"] == drupal_id
    assert "mark-read forbidden" in caplog.text
    assert "Forbidden by policy" in caplog.text


@pytest.mark.django_db
def test_reservation_messages_get_mark_read_server_error_does_not_break_page(
    sales_ui_salesperson_api_client, monkeypatch, caplog
):
    """Open chat should survive mark-read 500 and keep thread available."""

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=780,
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        thread_payload={
            "application_id": drupal_id,
            "count": 1,
            "items": [{"id": 1, "body": "first", "created": 1710000000}],
        },
        mark_read_to_raise=DrupalMessagingClientError(
            status_code=500,
            code="temporary_failure",
            message="Upstream unavailable",
        ),
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    with caplog.at_level("WARNING"):
        response = sales_ui_salesperson_api_client.get(
            reverse(
                "application_form:sales-apartment-reservation-messages",
                kwargs={"pk": reservation.id},
            )
        )

    assert response.status_code == 200
    assert response.data["application_id"] == drupal_id
    assert "mark-read temporary failure" in caplog.text


@pytest.mark.django_db
def test_reservation_messages_get_normalizes_message_field_to_body(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Thread response normalizes items for frontend compatibility.

    - Upstream may return message text in `message`/`text` instead of `body`.
    - API always returns item body as a string.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=778,
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        thread_payload={
            "application_id": drupal_id,
            "count": 2,
            "items": [
                {"id": 2, "text": "second", "created": 1710000100},
                {"id": 1, "message": "first", "created": 1710000000},
            ],
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["application_id"] == drupal_id
    assert response.data["items"][0]["body"] == "first"
    assert response.data["items"][1]["body"] == "second"
    assert "created_at" in response.data["items"][0]
    assert "T" in response.data["items"][0]["created_at"]
    assert "created_at" in response.data["items"][1]


@pytest.mark.django_db
def test_reservation_messages_post_success(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Salesperson can post a message for reservation's linked application.

    - Request body is forwarded to client.
    - Upstream created item is returned.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=888,
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        post_payload={
            "message": "Message created.",
            "item": {
                "id": 10,
                "application_id": drupal_id,
                "sender_role": "sales",
                "body": "Hei",
                "created": 1710000000,
            },
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "Hei"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["id"] == 10
    assert response.data["application_id"] == drupal_id
    assert response.data["body"] == "Hei"
    assert response.data["created"] == 1710000000
    assert "created_at" in response.data
    assert "T" in response.data["created_at"]
    assert fake_client.post_calls == [(drupal_id, "Hei", None)]


@pytest.mark.django_db
def test_reservation_messages_post_sends_co_applicant_email_when_known(
    sales_ui_salesperson_api_client, monkeypatch
):
    """POST includes co_applicant_email when secondary profile email exists.

    - sender_role remains sales.
    - Payload includes co_applicant_email for Drupal.
    """

    apartment = ApartmentDocumentFactory()
    secondary_profile = ProfileFactory(email="co.applicant@example.com")
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=890,
        application_apartment__application__customer__secondary_profile=(
            secondary_profile
        ),
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        post_payload={
            "message": "Message created.",
            "item": {
                "id": 12,
                "application_id": drupal_id,
                "sender_role": "sales",
                "body": "Hei",
                "created": 1710000002,
            },
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "Hei"},
        format="json",
    )

    assert response.status_code == 201
    assert fake_client.post_calls == [(drupal_id, "Hei", "co.applicant@example.com")]


@pytest.mark.django_db
def test_reservation_messages_post_success_normalizes_item_message_field(
    sales_ui_salesperson_api_client, monkeypatch
):
    """POST response normalizes message field to body in returned item.

    - Upstream item may contain message text in `message` instead of `body`.
    - API always returns flat ApartmentReservationMessage with body populated.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=889,
    )
    drupal_id = reservation.application_apartment.application.drupal_application_id

    fake_client = _FakeMessagingClient(
        post_payload={
            "message": "Message created.",
            "item": {
                "id": 11,
                "application_id": drupal_id,
                "sender_role": "sales",
                "message": "Hei maailma",
                "created": 1710000001,
            },
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "Hei maailma"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["id"] == 11
    assert response.data["application_id"] == drupal_id
    assert response.data["body"] == "Hei maailma"
    assert response.data["created"] == 1710000001


@pytest.mark.django_db
def test_reservation_messages_post_empty_body_validation(
    sales_ui_salesperson_api_client,
):
    """Empty message body is rejected by API validation.

    - Blank text returns 400.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "   "},
        format="json",
    )

    assert response.status_code == 400
    assert "body" in response.data


@pytest.mark.django_db
def test_reservation_messages_get_upstream_not_found(
    sales_ui_salesperson_api_client, monkeypatch
):
    """GET 404 from Drupal is tolerated for legacy data.

    - Missing application in Drupal returns 200 with empty thread.
    """

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    fake_client = _FakeMessagingClient(
        to_raise=DrupalMessagingClientError(status_code=404, code="not_found")
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert (
        response.data["application_id"]
        == reservation.application_apartment.application.drupal_application_id
    )
    assert response.data["count"] == 0
    assert response.data["items"] == []


@pytest.mark.django_db
def test_reservation_messages_get_without_linked_application_returns_empty_thread(
    sales_ui_salesperson_api_client,
):
    """GET with no linked application is tolerated for legacy reservations.

    - Reservation without linked application returns 200 with empty thread.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["application_id"] is None
    assert response.data["count"] == 0
    assert response.data["items"] == []


@pytest.mark.django_db
def test_reservation_messages_post_upstream_forbidden(
    sales_ui_salesperson_api_client, monkeypatch
):
    """403 from Drupal is mapped to a clear permission error.

    - Forbidden upstream response returns 403 in Django API.
    """

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    fake_client = _FakeMessagingClient(
        to_raise=DrupalMessagingClientError(status_code=403, code="forbidden")
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "test"},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["detail"] == "Insufficient permissions."


@pytest.mark.django_db
def test_reservation_messages_post_upstream_temporary_error(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Temporary upstream failures are mapped to neutral retry message.

    - Temporary error returns 503.
    - User-facing message remains non-technical.
    """

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=999,
    )

    fake_client = _FakeMessagingClient(
        to_raise=DrupalMessagingClientError(
            status_code=503,
            code="temporary_failure",
            message="technical details",
        )
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "test"},
        format="json",
    )

    assert response.status_code == 503
    assert response.data["detail"] == "Messaging service temporarily unavailable."


@pytest.mark.django_db
def test_reservation_messages_get_no_drupal_id_returns_empty_thread(
    sales_ui_salesperson_api_client,
):
    """GET messages when drupal_application_id is None returns empty thread.

    - Application has no drupal_application_id.
    - No Drupal API call is made.
    - Response is 200 with count=0 and empty items list.
    - Frontend shows "no messages" without an error.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["count"] == 0
    assert response.data["items"] == []


@pytest.mark.django_db
def test_reservation_messages_post_no_drupal_id_returns_503(
    sales_ui_salesperson_api_client,
):
    """POST message when drupal_application_id is None returns 503.

    - Application has no drupal_application_id.
    - No Drupal API call is made.
    - Response is 503 so frontend can show a neutral retry message.
    """
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=None,
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        data={"body": "Hello"},
        format="json",
    )

    assert response.status_code == 503
    assert "detail" in response.data


@pytest.mark.django_db
def test_reservation_messages_unread_counts_success(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Unread proxy returns Drupal payload using sales_shared mode.

    - Sends viewer_role="sales".
    - Does not send application_ids in the default request.
    """

    fake_client = _FakeMessagingClient(
        thread_payload={"counts": {"131": 1, "132": 0}, "total": 1}
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-unread-counts")
    )

    assert response.status_code == 200
    assert response.data == {"counts": {"131": 1, "132": 0}, "total": 1}
    assert fake_client.unread_calls == [("sales", None)]
    assert response["Cache-Control"] == "no-store, no-cache, private"


@pytest.mark.django_db
def test_reservation_messages_unread_counts_retries_on_invalid_request(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Unread proxy retries legacy contract when ids are required upstream.

    - First request is sales_shared without application_ids.
    - If upstream returns invalid_request, retries with application_ids.
    """

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    ApartmentReservationFactory(
        application_apartment__application__drupal_application_id=131,
    )
    ApartmentReservationFactory(
        application_apartment__application__drupal_application_id=132,
    )

    class _FallbackClient(_FakeMessagingClient):
        def get_unread_counts(self, *, viewer_role, application_ids=None):
            self.unread_calls.append((viewer_role, application_ids))
            if application_ids is None:
                raise DrupalMessagingClientError(
                    status_code=400,
                    code="invalid_request",
                )
            return {"counts": {"131": 1}, "total": 1}

    fake_client = _FallbackClient()
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-unread-counts")
    )

    assert response.status_code == 200
    assert response.data == {"counts": {"131": 1}, "total": 1}
    assert fake_client.unread_calls[0] == ("sales", None)
    assert fake_client.unread_calls[1][0] == "sales"
    assert isinstance(fake_client.unread_calls[1][1], list)
    assert fake_client.unread_calls[1][1]


@pytest.mark.django_db
def test_reservation_messages_unread_counts_fallback_on_forbidden(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Forbidden upstream unread response falls back to empty counters."""

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    fake_client = _FakeMessagingClient(
        to_raise=DrupalMessagingClientError(status_code=403, code="forbidden")
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-unread-counts")
    )

    assert response.status_code == 200
    assert response.data == {"counts": {}, "total": 0}


@pytest.mark.django_db
def test_reservation_messages_inbox_summary_success(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Inbox summary returns Drupal payload enriched with deep-link IDs."""

    fake_client = _FakeMessagingClient(
        inbox_payload={
            "items": [
                {
                    "application_id": 131,
                    "unread_count": 3,
                    "last_message_at": "2026-09-29T07:03:01+00:00",
                    "last_message_preview": "Moi, olen paikalla!",
                    "has_unread": True,
                }
            ],
            "total_unread": 3,
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )
    monkeypatch.setattr(
        (
            "application_form.api.sales.views."
            "_get_sales_inbox_summary_context_by_drupal_application_id"
        ),
        lambda _application_ids: {
            131: {
                "customer_id": 77,
                "project_uuid": "7972c85d-c78e-4250-9e33-0cc14abeff1a",
                "reservation_id": 999,
                "project_id": 321,
                "project_name": "Test Project",
                "applicant_name": "Jane Doe",
            }
        },
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-inbox-summary")
    )

    assert response.status_code == 200
    assert response.data["total_unread"] == 3
    assert response.data["items"][0]["application_id"] == 131
    assert response.data["items"][0]["customer_id"] == 77
    assert (
        str(response.data["items"][0]["project_uuid"])
        == "7972c85d-c78e-4250-9e33-0cc14abeff1a"
    )
    assert response.data["items"][0]["reservation_id"] == 999
    assert response.data["items"][0]["project_id"] == 321
    assert response.data["items"][0]["applicant_name"] == "Jane Doe"
    assert response.data["items"][0]["project_name"] == "Test Project"
    assert fake_client.inbox_calls == [("sales", None)]
    assert response["Cache-Control"] == "no-store, no-cache, private"


@pytest.mark.django_db
def test_reservation_messages_inbox_summary_retries_with_application_ids(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Inbox summary retries legacy contract when ids are required upstream."""

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    ApartmentReservationFactory(
        application_apartment__application__drupal_application_id=131,
    )

    class _FallbackClient(_FakeMessagingClient):
        def get_inbox_summary(self, *, viewer_role, application_ids=None):
            self.inbox_calls.append((viewer_role, application_ids))
            if application_ids is None:
                raise DrupalMessagingClientError(
                    status_code=400,
                    code="invalid_request",
                )
            return {
                "items": [
                    {
                        "application_id": 131,
                        "unread_count": 1,
                        "last_message_at": "2026-09-29T07:03:01+00:00",
                        "last_message_preview": "Hei",
                        "has_unread": True,
                    }
                ],
                "total_unread": 1,
            }

    fake_client = _FallbackClient()
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )
    monkeypatch.setattr(
        (
            "application_form.api.sales.views."
            "_get_sales_inbox_summary_context_by_drupal_application_id"
        ),
        lambda _application_ids: {
            131: {
                "customer_id": 11,
                "project_uuid": "8a93072b-7697-4bd1-99f8-9691a44cc9d2",
                "reservation_id": 123,
                "project_id": None,
                "project_name": "",
                "applicant_name": "",
            }
        },
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-inbox-summary")
    )

    assert response.status_code == 200
    assert response.data["total_unread"] == 1
    assert response.data["items"][0]["customer_id"] == 11
    assert (
        str(response.data["items"][0]["project_uuid"])
        == "8a93072b-7697-4bd1-99f8-9691a44cc9d2"
    )
    assert response.data["items"][0]["reservation_id"] == 123
    assert fake_client.inbox_calls[0] == ("sales", None)
    assert fake_client.inbox_calls[1][0] == "sales"
    assert isinstance(fake_client.inbox_calls[1][1], list)


@pytest.mark.django_db
def test_reservation_messages_inbox_summary_fallback_on_forbidden(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Forbidden inbox summary upstream response falls back to empty payload."""

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    fake_client = _FakeMessagingClient(
        to_raise=DrupalMessagingClientError(status_code=403, code="forbidden")
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-inbox-summary")
    )

    assert response.status_code == 200
    assert response.data == {"items": [], "total_unread": 0}


@pytest.mark.django_db
def test_reservation_messages_inbox_summary_skips_items_without_deeplink_context(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Items missing local deep-link IDs are skipped without hard failure."""

    fake_client = _FakeMessagingClient(
        inbox_payload={
            "items": [
                {
                    "application_id": 131,
                    "unread_count": 2,
                    "last_message_at": "2026-09-29T07:03:01+00:00",
                    "last_message_preview": "Hei",
                    "has_unread": True,
                }
            ],
            "total_unread": 2,
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )
    monkeypatch.setattr(
        (
            "application_form.api.sales.views."
            "_get_sales_inbox_summary_context_by_drupal_application_id"
        ),
        lambda _application_ids: {},
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-inbox-summary")
    )

    assert response.status_code == 200
    assert response.data == {"items": [], "total_unread": 0}


@pytest.mark.django_db
def test_reservation_messages_inbox_summary_excludes_read_items(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Inbox summary should contain only unread items for sales badge/list."""

    fake_client = _FakeMessagingClient(
        inbox_payload={
            "items": [
                {
                    "application_id": 131,
                    "unread_count": 0,
                    "last_message_at": "2026-09-29T07:03:01+00:00",
                    "last_message_preview": "Hei",
                    "has_unread": False,
                }
            ],
            "total_unread": 0,
        }
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.IsDrupalSalesperson.has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )
    monkeypatch.setattr(
        (
            "application_form.api.sales.views."
            "_get_sales_inbox_summary_context_by_drupal_application_id"
        ),
        lambda _application_ids: {
            131: {
                "customer_id": 18,
                "project_uuid": "8a93072b-7697-4bd1-99f8-9691a44cc9d2",
                "reservation_id": 242,
                "project_id": 2962,
                "project_name": "2025 Haso Hakemus",
                "applicant_name": "First Customer",
            }
        },
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("application_form:sales-application-inbox-summary")
    )

    assert response.status_code == 200
    assert response.data == {"items": [], "total_unread": 0}
