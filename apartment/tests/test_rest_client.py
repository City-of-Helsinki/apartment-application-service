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
