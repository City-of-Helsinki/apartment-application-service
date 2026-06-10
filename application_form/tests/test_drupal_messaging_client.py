import requests

import pytest

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

    def fake_request(method, url, headers=None, timeout=None, json=None, verify=None):
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

    def fake_request(method, url, json=None, headers=None, timeout=None, verify=None):
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

    def fake_request(method, url, headers=None, timeout=None, json=None, verify=None):
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
