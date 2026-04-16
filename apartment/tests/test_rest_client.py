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


def test_drupal_search_client_translates_offset_limit_to_page_size(
    settings, monkeypatch
):
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

    assert captured["params"]["page"] == 6
    assert captured["params"]["size"] == 100
    assert "offset" not in captured["params"]
    assert "limit" not in captured["params"]


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
