import pytest
from django.urls import reverse

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory


class _FakeMessagingClient:
    def __init__(self, thread_payload=None, post_payload=None, to_raise=None):
        self._thread_payload = thread_payload
        self._post_payload = post_payload
        self._to_raise = to_raise
        self.get_calls = []
        self.post_calls = []

    def get_thread(self, application_id):
        self.get_calls.append(application_id)
        if self._to_raise:
            raise self._to_raise
        return self._thread_payload

    def post_sales_reply(self, application_id, body):
        self.post_calls.append((application_id, body))
        if self._to_raise:
            raise self._to_raise
        return self._post_payload


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
    assert [item["id"] for item in response.data["items"]] == [1, 2]
    assert fake_client.get_calls == [drupal_id]


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
    assert fake_client.post_calls == [(drupal_id, "Hei")]


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
    """404 from Drupal is mapped to a clear business error.

    - Missing application returns 404 in Django API.
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

    assert response.status_code == 404
    assert response.data["detail"] == "Application not found."


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
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

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
    assert (
        response.data["detail"] == "Не удалось отправить сообщение, попробуйте еще раз."
    )


@pytest.mark.django_db
def test_reservation_messages_get_uses_application_pk_when_drupal_id_missing(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Legacy reservations use application pk as Drupal application id fallback.

    - Application has no drupal_application_id.
    - API uses application.id when fetching thread.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=None,
    )
    fallback_id = reservation.application_apartment.application.id

    fake_client = _FakeMessagingClient(
        thread_payload={
            "application_id": fallback_id,
            "count": 1,
            "items": [{"id": 1, "body": "legacy", "created": 1710000000}],
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
    assert response.data["application_id"] == fallback_id
    assert fake_client.get_calls == [fallback_id]


@pytest.mark.django_db
def test_reservation_messages_no_drupal_id_fallback_not_found_returns_404(
    sales_ui_salesperson_api_client, monkeypatch
):
    """If legacy fallback id is missing in Drupal, API still returns 404.

    - Application has no drupal_application_id.
    - API falls back to application.id and maps Drupal 404 to business 404.
    """

    from application_form.services.drupal_messaging import DrupalMessagingClientError

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=None,
    )
    fallback_id = reservation.application_apartment.application.id

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

    assert response.status_code == 404
    assert response.data["detail"] == "Application not found."
    assert fake_client.get_calls == [fallback_id]


@pytest.mark.django_db
def test_reservation_messages_get_with_matching_project_uuid(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Matching project_uuid query parameter allows loading the thread.

    - Reservation apartment project matches query parameter.
    - API responds successfully.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=901,
    )

    fake_client = _FakeMessagingClient(
        thread_payload={
            "application_id": 901,
            "count": 1,
            "items": [{"id": 1, "body": "ok", "created": 1710000000}],
        }
    )

    class _Apartment:
        project_uuid = "8a93072b-7697-4bd1-99f8-9691a44cc9d2"

    monkeypatch.setattr(
        "application_form.api.sales.views.DrupalMessagingClient",
        lambda: fake_client,
    )
    monkeypatch.setattr(
        "application_form.api.sales.views.get_apartment",
        lambda *args, **kwargs: _Apartment(),
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        {"project_uuid": "8a93072b-7697-4bd1-99f8-9691a44cc9d2"},
    )

    assert response.status_code == 200
    assert fake_client.get_calls == [901]


@pytest.mark.django_db
def test_reservation_messages_get_with_mismatching_project_uuid_returns_400(
    sales_ui_salesperson_api_client, monkeypatch
):
    """Mismatching project_uuid query parameter is rejected.

    - Reservation apartment project does not match query parameter.
    - API returns validation error.
    """

    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment__application__drupal_application_id=902,
    )

    class _Apartment:
        project_uuid = "8a93072b-7697-4bd1-99f8-9691a44cc9d2"

    monkeypatch.setattr(
        "application_form.api.sales.views.get_apartment",
        lambda *args, **kwargs: _Apartment(),
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-messages",
            kwargs={"pk": reservation.id},
        ),
        {"project_uuid": "e77dc4ec-e4f6-4b2f-b82d-76a5e4ea7022"},
    )

    assert response.status_code == 400
    assert (
        response.data["detail"]
        == "Reservation does not belong to the requested project."
    )
