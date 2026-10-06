import pytest
import requests

from application_form.services.drupal_messaging import (
    DrupalMessagingClient,
    DrupalMessagingClientError,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


def _configure_drupal_search_settings(settings):
    settings.DRUPAL_SEARCH_API_BASE_URL = "https://drupal.example"
    settings.DRUPAL_SEARCH_API_TOKEN_URL = "https://drupal.example/oauth/token"
    settings.DRUPAL_SEARCH_API_CLIENT_ID = "client-id"
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = "client-secret"
    settings.DRUPAL_SEARCH_API_TIMEOUT = 3
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = True
    settings.DRUPAL_SEARCH_API_RETRY_COUNT = 1


@pytest.mark.django_db
def test_get_thread_uses_cached_oauth_token(settings, monkeypatch):
    """Ensure the OAuth token is fetched once and reused.

    - First request obtains token and fetches thread.
    - Second request reuses cached token.
    """

    _configure_drupal_search_settings(settings)

    counters = {"token_calls": 0, "api_calls": 0}

    def fake_post(url, data=None, headers=None, timeout=None, verify=None):
        counters["token_calls"] += 1
        assert url == settings.DRUPAL_SEARCH_API_TOKEN_URL
        assert data["grant_type"] == "client_credentials"
        return _FakeResponse(
            status_code=200,
            payload={"access_token": "cached-token", "expires_in": 3600},
        )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        counters["api_calls"] += 1
        assert method == "GET"
        assert headers["Authorization"] == "Bearer cached-token"
        return _FakeResponse(
            status_code=200,
            payload={"application_id": 12, "count": 0, "items": []},
        )

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    assert client.get_thread(12)["application_id"] == 12
    assert client.get_thread(12)["application_id"] == 12
    assert counters["token_calls"] == 1
    assert counters["api_calls"] == 2


@pytest.mark.django_db
def test_post_sales_reply_sends_expected_payload(settings, monkeypatch):
    """Verify POST payload includes sales sender role.

    - Sends user body as-is.
    - Enforces sender_role="sales".
    """
    from django.core.cache import cache as django_cache

    django_cache.clear()

    _configure_drupal_search_settings(settings)

    captured = {}

    def fake_token_post(url, data=None, headers=None, timeout=None, verify=None):
        return _FakeResponse(
            status_code=200,
            payload={"access_token": "token-post", "expires_in": 3600},
        )

    def fake_request(
        method,
        url,
        json=None,
        headers=None,
        timeout=None,
        data=None,
        params=None,
        verify=None,
    ):
        assert method == "POST"
        captured["url"] = url
        captured["payload"] = json
        captured["auth"] = headers.get("Authorization")
        return _FakeResponse(
            status_code=201,
            payload={"item": {"id": 1, "application_id": 12, "body": "hello"}},
        )

    monkeypatch.setattr(requests, "post", fake_token_post)
    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.post_sales_reply(12, "hello")

    assert payload["item"]["body"] == "hello"
    assert captured["url"] == "https://drupal.example/applications/12/messages"
    assert captured["payload"] == {"body": "hello", "sender_role": "sales"}
    assert captured["auth"] == "Bearer token-post"


@pytest.mark.django_db
def test_post_sales_reply_includes_co_applicant_email_when_given(settings, monkeypatch):
    """Verify POST payload includes co_applicant_email when available.

    - Sends user body as-is.
    - Enforces sender_role="sales".
    - Includes co_applicant_email when provided.
    """
    from django.core.cache import cache as django_cache

    django_cache.clear()
    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-post", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        json=None,
        headers=None,
        timeout=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["payload"] = json
        return _FakeResponse(
            status_code=201,
            payload={"item": {"id": 2, "application_id": 12, "body": "hello"}},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    client.post_sales_reply(
        12,
        "hello",
        co_applicant_email="co.applicant@example.com",
    )

    assert captured["payload"] == {
        "body": "hello",
        "sender_role": "sales",
        "co_applicant_email": "co.applicant@example.com",
    }


@pytest.mark.django_db
def test_post_sales_reply_omits_blank_co_applicant_email(settings, monkeypatch):
    """Blank co_applicant_email should not break integration payload.

    - Request is still sent successfully.
    - Payload omits co_applicant_email when blank.
    """
    from django.core.cache import cache as django_cache

    django_cache.clear()
    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-post", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        json=None,
        headers=None,
        timeout=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["payload"] = json
        return _FakeResponse(
            status_code=201,
            payload={"item": {"id": 3, "application_id": 12, "body": "hello"}},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    client.post_sales_reply(12, "hello", co_applicant_email="   ")

    assert captured["payload"] == {"body": "hello", "sender_role": "sales"}


@pytest.mark.django_db
def test_post_sales_reply_logs_co_applicant_presence(settings, monkeypatch, caplog):
    """Debug log should include metadata without exposing email value.

    - Logs application_id and sender_role.
    - Logs only whether co_applicant_email was included.
    """
    from django.core.cache import cache as django_cache

    django_cache.clear()
    _configure_drupal_search_settings(settings)

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-post", "expires_in": 3600},
        ),
    )
    monkeypatch.setattr(
        requests,
        "request",
        lambda *args, **kwargs: _FakeResponse(
            status_code=201,
            payload={"item": {"id": 4, "application_id": 12, "body": "hello"}},
        ),
    )

    client = DrupalMessagingClient()
    with caplog.at_level("DEBUG"):
        client.post_sales_reply(
            12,
            "hello",
            co_applicant_email="co.applicant@example.com",
        )

    assert "application_id=12" in caplog.text
    assert "sender_role=sales" in caplog.text
    assert "co_applicant_email_included=True" in caplog.text
    assert "co.applicant@example.com" not in caplog.text


@pytest.mark.django_db
def test_post_sales_reply_accepts_http_200_success(settings, monkeypatch):
    """POST success should accept 200 from upstream.

    Some Drupal environments return 200 for message POST even when message
    creation succeeds.
    """
    from django.core.cache import cache as django_cache

    django_cache.clear()
    _configure_drupal_search_settings(settings)

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-post", "expires_in": 3600},
        ),
    )
    monkeypatch.setattr(
        requests,
        "request",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"item": {"id": 2, "application_id": 12, "body": "hello"}},
        ),
    )

    client = DrupalMessagingClient()
    payload = client.post_sales_reply(12, "hello")

    assert payload["item"]["id"] == 2


@pytest.mark.django_db
def test_request_retries_on_server_errors(settings, monkeypatch):
    """Retry should be attempted for transient 5xx responses.

    - First two responses are 500.
    - Third response succeeds.
    """
    from django.core.cache import cache as django_cache

    django_cache.clear()

    _configure_drupal_search_settings(settings)
    settings.DRUPAL_SEARCH_API_RETRY_COUNT = 3

    token_calls = {"count": 0}
    request_calls = {"count": 0}

    def fake_post(url, data=None, headers=None, timeout=None, verify=None):
        token_calls["count"] += 1
        return _FakeResponse(
            status_code=200,
            payload={"access_token": "token-retry", "expires_in": 3600},
        )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        request_calls["count"] += 1
        if request_calls["count"] < 3:
            return _FakeResponse(status_code=500, payload={"message": "error"})
        return _FakeResponse(
            status_code=200,
            payload={"application_id": 12, "count": 0, "items": []},
        )

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    result = client.get_thread(12)

    assert result["application_id"] == 12
    assert token_calls["count"] == 1
    assert request_calls["count"] == 3


@pytest.mark.django_db
def test_get_thread_raises_for_not_found(settings, monkeypatch):
    """A 404 response should be surfaced with status code.

    - Client raises structured integration error.
    - Error includes upstream status code.
    """

    _configure_drupal_search_settings(settings)

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-1", "expires_in": 3600},
        ),
    )
    monkeypatch.setattr(
        requests,
        "request",
        lambda *args, **kwargs: _FakeResponse(
            status_code=404, payload={"message": "not found"}
        ),
    )

    client = DrupalMessagingClient()
    with pytest.raises(DrupalMessagingClientError) as exc_info:
        client.get_thread(999)

    assert exc_info.value.status_code == 404


@pytest.mark.django_db
def test_post_sales_reply_raises_after_retryable_network_errors(settings, monkeypatch):
    """Network-level failures should be retried and then fail gracefully.

    - All attempts raise request exception.
    - Client raises a structured temporary integration error.
    """

    _configure_drupal_search_settings(settings)
    settings.DRUPAL_SEARCH_API_RETRY_COUNT = 2

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-1", "expires_in": 3600},
        ),
    )

    def fake_request(*args, **kwargs):
        raise requests.RequestException("temporary network issue")

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    with pytest.raises(DrupalMessagingClientError) as exc_info:
        client.post_sales_reply(77, "hello")

    assert exc_info.value.code == "temporary_failure"


@pytest.mark.django_db
def test_get_unread_counts_sales_shared_without_application_ids(settings, monkeypatch):
    """Sales unread query defaults to shared mode without ids payload."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-unread", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["params"] = params
        return _FakeResponse(
            status_code=200,
            payload={"counts": {"131": 1}, "total": 1},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.get_unread_counts(viewer_role="sales")

    assert payload == {"counts": {"131": 1}, "total": 1}
    assert captured["params"] == {
        "viewer_role": "sales",
        "sales_shared": "1",
    }


@pytest.mark.django_db
def test_get_unread_counts_sends_sales_shared_and_application_ids(
    settings, monkeypatch
):
    """Sales unread query includes shared-sales and application filter params."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-unread", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(
            status_code=200,
            payload={"counts": {"131": 1}, "total": 1},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.get_unread_counts(
        viewer_role="sales",
        application_ids=[131, 132],
    )

    assert payload == {"counts": {"131": 1}, "total": 1}
    assert captured["method"] == "GET"
    assert captured["url"] == "https://drupal.example/user/application/unread-counts"
    assert captured["params"] == {
        "viewer_role": "sales",
        "sales_shared": "1",
        "application_ids": "131,132",
    }


@pytest.mark.django_db
def test_get_unread_counts_customer_role_does_not_send_sales_shared(
    settings, monkeypatch
):
    """Customer unread query must not include sales_shared parameter."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-unread", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["params"] = params
        return _FakeResponse(
            status_code=200,
            payload={"counts": {}, "total": 0},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.get_unread_counts(viewer_role="customer")

    assert payload == {"counts": {}, "total": 0}
    assert captured["params"] == {"viewer_role": "customer"}


@pytest.mark.django_db
def test_get_inbox_summary_sales_shared_without_application_ids(settings, monkeypatch):
    """Sales inbox summary defaults to shared mode without ids payload."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-inbox", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["params"] = params
        return _FakeResponse(
            status_code=200,
            payload={"items": [], "total_unread": 0},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.get_inbox_summary(viewer_role="sales")

    assert payload == {"items": [], "total_unread": 0}
    assert captured["params"] == {
        "viewer_role": "sales",
        "sales_shared": "1",
    }


@pytest.mark.django_db
def test_get_inbox_summary_sends_sales_shared_and_application_ids(
    settings, monkeypatch
):
    """Sales inbox summary supports legacy application_ids filter."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-inbox", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(
            status_code=200,
            payload={"items": [], "total_unread": 0},
        )

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.get_inbox_summary(
        viewer_role="sales",
        application_ids=[110, 131],
    )

    assert payload == {"items": [], "total_unread": 0}
    assert captured["method"] == "GET"
    assert captured["url"] == "https://drupal.example/user/application/inbox-summary"
    assert captured["params"] == {
        "viewer_role": "sales",
        "sales_shared": "1",
        "application_ids": "110,131",
    }


@pytest.mark.django_db
def test_post_mark_read_sends_sales_shared_and_application_id(settings, monkeypatch):
    """Sales mark-read uses shared mode with form body application_id."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-read", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["data"] = data
        captured["params"] = params
        return _FakeResponse(status_code=200, payload={"status": "ok"})

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    payload = client.post_mark_read(
        viewer_role="sales",
        application_id=131,
    )

    assert payload == {"status": "ok"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://drupal.example/user/application/mark-read"
    assert captured["params"] == {
        "viewer_role": "sales",
        "sales_shared": "1",
    }
    assert captured["json"] is None
    assert captured["data"] == {"application_id": "131"}
    assert captured["headers"]["Content-Type"] == "application/x-www-form-urlencoded"


@pytest.mark.django_db
def test_post_mark_read_sends_application_ids_list(settings, monkeypatch):
    """Sales mark-read supports batch application_ids form field."""

    _configure_drupal_search_settings(settings)

    captured = {}

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"access_token": "token-read", "expires_in": 3600},
        ),
    )

    def fake_request(
        method,
        url,
        headers=None,
        timeout=None,
        json=None,
        data=None,
        params=None,
        verify=None,
    ):
        captured["data"] = data
        return _FakeResponse(status_code=200, payload={"status": "ok"})

    monkeypatch.setattr(requests, "request", fake_request)

    client = DrupalMessagingClient()
    client.post_mark_read(
        viewer_role="sales",
        application_ids=[131, 132, 133],
    )

    assert captured["data"] == {"application_ids": "131,132,133"}
