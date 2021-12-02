import faker.config
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection
from pytest import fixture, skip
from rest_framework.test import APIClient

from apartment.tests.factories import ApartmentDocumentFactory

faker.config.DEFAULT_LOCALE = "fi_FI"


@fixture
def api_client():
    api_client = APIClient()
    return api_client


@fixture(autouse=True, scope="session")
def elastic_client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
        connection.indices.delete("test-*", ignore=404)
    except SkipTest:
        skip()


@fixture(scope="session")
def elastic_apartments():
    yield ApartmentDocumentFactory.build_batch_and_save_elastic(10)
