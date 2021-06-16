import faker.config
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection
from pytest import fixture, skip
from rest_framework.test import APIClient

from connections.tests.factories import ApartmentMinimalFactory

faker.config.DEFAULT_LOCALE = "fi_FI"


@fixture(scope="session")
def api_client():
    return APIClient()


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
    elastic_apartments = ApartmentMinimalFactory.build_for_sale_batch(10)
    try:
        for item in elastic_apartments:
            item.save(refresh="wait_for")
        yield elastic_apartments
    except SkipTest:
        skip()
