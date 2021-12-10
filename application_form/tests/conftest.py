import faker.config
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection, get_connection
from pytest import fixture, skip
from rest_framework.test import APIClient

from connections.tests.factories import ApartmentMinimalFactory

faker.config.DEFAULT_LOCALE = "fi_FI"


@fixture
def api_client():
    return APIClient()


@fixture(autouse=True, scope="session")
def elastic_client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
    except SkipTest:
        skip()


@fixture(scope="session")
def elastic_apartments():
    connection = get_connection()
    connection.indices.delete("test-*", ignore=404)
    yield ApartmentMinimalFactory.create_for_sale_batch(10)
