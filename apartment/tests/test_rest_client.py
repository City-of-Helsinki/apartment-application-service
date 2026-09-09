import requests

from apartment.elastic.rest_client import DrupalSearchClient


def test_drupal_search_client_sets_accept_language_header(settings, monkeypatch):
    settings.DRUPAL_SEARCH_API_BASE_URL = "http://example.com"
    settings.DRUPAL_SEARCH_API_TOKEN_URL = ""
    settings.DRUPAL_SEARCH_API_CLIENT_ID = ""
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = ""
    settings.DRUPAL_SEARCH_API_TIMEOUT = 1
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = True
    settings.LANGUAGE_CODE = "fi"

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        captured["headers"] = headers

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    client = DrupalSearchClient()
    client.get("projects")

    assert captured["headers"]["Accept-Language"] == "fi"


def test_drupal_search_client_get_is_cached(settings, monkeypatch):
    settings.DRUPAL_SEARCH_API_BASE_URL = "http://example.com"
    settings.DRUPAL_SEARCH_API_TOKEN_URL = ""
    settings.DRUPAL_SEARCH_API_CLIENT_ID = ""
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = ""
    settings.DRUPAL_SEARCH_API_TIMEOUT = 1
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = True
    settings.LANGUAGE_CODE = "fi"
    settings.DRUPAL_SEARCH_API_GET_CACHE_SECONDS = 60

    from django.core.cache import cache

    cache.clear()

    calls = {"count": 0}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        calls["count"] += 1

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True, "params": params, "url": url}

        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    client = DrupalSearchClient()
    first = client.get("apartments", params={"offset": 500, "limit": 100})
    second = client.get("apartments", params={"offset": 500, "limit": 100})

    assert first == second
    assert calls["count"] == 1


def test_normalize_pagination_params_maps_limit_offset_to_size_from():
    """
    Drupal getPaginationWithPage uses `from` when present.

    - limit is sent as size.
    - offset is sent as from, not converted to page.
    """
    client = DrupalSearchClient()
    result = client._normalize_pagination_params({"limit": 100, "offset": 500})

    assert result["size"] == 100
    assert result["from"] == 500
    assert "page" not in result
    assert "offset" not in result
    assert "limit" not in result


def test_normalize_pagination_params_does_not_map_offset_to_page_one():
    """
    offset=250 with size=1000 must not become page=1.

    - Old page math used offset // size, which repeats the first page.
    - Drupal then serves hits 0-249 again instead of 250-499.
    """
    client = DrupalSearchClient()
    result = client._normalize_pagination_params({"limit": 1000, "offset": 250})

    assert result["from"] == 250
    assert result["size"] == 1000
    assert "page" not in result


def test_normalize_pagination_params_maps_zero_offset_to_from():
    """
    offset=0 must be sent as from, not converted to page=1.

    - Drupal honors from when present.
    - Mixing page and from makes capped page sizes skip or repeat hits.
    """
    client = DrupalSearchClient()
    result = client._normalize_pagination_params({"limit": 250, "offset": 0})

    assert result["from"] == 0
    assert result["size"] == 250
    assert "page" not in result


def test_normalize_pagination_params_keeps_explicit_page():
    """
    An explicit page parameter must win over offset.

    - page stays 3.
    - offset is dropped so Drupal does not mix from and page.
    """
    client = DrupalSearchClient()
    result = client._normalize_pagination_params({"page": 3, "size": 25, "offset": 100})

    assert result["page"] == 3
    assert result["size"] == 25
    assert "offset" not in result
    assert "from" not in result


def test_drupal_search_client_translates_offset_limit_to_from_size(
    settings, monkeypatch
):
    """
    HTTP GET must send from+size so Drupal honors the absolute offset.

    - offset 500, limit 100 -> from=500, size=100.
    - page is absent (Drupal would otherwise recompute offset from capped size).
    """
    settings.DRUPAL_SEARCH_API_BASE_URL = "http://example.com"
    settings.DRUPAL_SEARCH_API_TOKEN_URL = ""
    settings.DRUPAL_SEARCH_API_CLIENT_ID = ""
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = ""
    settings.DRUPAL_SEARCH_API_TIMEOUT = 1
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = True
    settings.LANGUAGE_CODE = "fi"

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        captured["params"] = params

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    client = DrupalSearchClient()
    client.get("apartments", params={"offset": 500, "limit": 100})

    assert captured["params"]["from"] == 500
    assert captured["params"]["size"] == 100
    assert "page" not in captured["params"]
    assert "offset" not in captured["params"]
    assert "limit" not in captured["params"]


def test_drupal_search_client_sends_from_when_offset_is_below_requested_size(
    settings, monkeypatch
):
    """
    A follow-up page after a 250-hit Drupal cap must not request page 1.

    - offset=250, limit=1000 used to become page=1 (250 // 1000 + 1).
    """
    settings.DRUPAL_SEARCH_API_BASE_URL = "http://example.com"
    settings.DRUPAL_SEARCH_API_TOKEN_URL = ""
    settings.DRUPAL_SEARCH_API_CLIENT_ID = ""
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = ""
    settings.DRUPAL_SEARCH_API_TIMEOUT = 1
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = True
    settings.LANGUAGE_CODE = "fi"

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        captured["params"] = params

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    client = DrupalSearchClient()
    client.get("apartments", params={"offset": 250, "limit": 1000})

    assert captured["params"]["from"] == 250
    assert captured["params"]["size"] == 1000
    assert "page" not in captured["params"]


def test_drupal_search_client_keeps_explicit_page(settings, monkeypatch):
    settings.DRUPAL_SEARCH_API_BASE_URL = "http://example.com"
    settings.DRUPAL_SEARCH_API_TOKEN_URL = ""
    settings.DRUPAL_SEARCH_API_CLIENT_ID = ""
    settings.DRUPAL_SEARCH_API_CLIENT_SECRET = ""
    settings.DRUPAL_SEARCH_API_TIMEOUT = 1
    settings.DRUPAL_SEARCH_API_VERIFY_SSL = True
    settings.LANGUAGE_CODE = "fi"

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        captured["params"] = params

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    client = DrupalSearchClient()
    client.get("apartments", params={"page": 3, "size": 25, "offset": 100})

    assert captured["params"]["page"] == 3
    assert captured["params"]["size"] == 25
    assert "offset" not in captured["params"]
