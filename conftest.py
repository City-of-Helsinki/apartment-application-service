import pytest

from apartment.tests.factories import (
    clear_apartment_store,
)


@pytest.fixture(autouse=True)
def clear_store_between_tests():
    clear_apartment_store()
    yield
    clear_apartment_store()


@pytest.fixture(autouse=True)
def mock_search_api(monkeypatch):
    from apartment.elastic import queries, rest_client
    from apartment.tests.utils import TestDrupalSearchClient

    monkeypatch.setattr(
        rest_client, "DrupalSearchClient", TestDrupalSearchClient, raising=True
    )
    monkeypatch.setattr(
        queries, "DrupalSearchClient", TestDrupalSearchClient, raising=True
    )
    queries._client = None


