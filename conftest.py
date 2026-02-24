import pytest

from apartment.tests.factories import clear_apartment_store


def pytest_addoption(parser):
    parser.addoption(
        "--integration-tests",
        action="store_true",
        default=False,
        help="Run integration tests (skipped by default)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (use --integration-tests)"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--integration-tests", default=False):
        return
    skip_integration = pytest.mark.skip(reason="needs --integration-tests to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


integration_test = pytest.mark.integration


@pytest.fixture(autouse=True)
def clear_store_between_tests():
    clear_apartment_store()
    yield
    clear_apartment_store()


@pytest.fixture(autouse=True)
def mock_search_api(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return
    from apartment.elastic import queries, rest_client
    from apartment.tests.utils import TestDrupalSearchClient

    monkeypatch.setattr(
        rest_client, "DrupalSearchClient", TestDrupalSearchClient, raising=True
    )
    monkeypatch.setattr(
        queries, "DrupalSearchClient", TestDrupalSearchClient, raising=True
    )
    queries._client = None


