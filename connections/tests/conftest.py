from pytest import fixture, skip
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection


@fixture(scope="session")
def client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
        connection.indices.delete("test-*", ignore=404)
    except SkipTest:
        skip()
