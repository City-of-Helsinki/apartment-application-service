from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection
from pytest import fixture, skip
from time import sleep

from connections.tests.factories import ApartmentMinimalFactory


@fixture(scope="class")
def client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
        connection.indices.delete("test-*", ignore=404)
    except SkipTest:
        skip()


@fixture(scope="class")
def elastic_apartments():
    try:
        elastic_apartments = ApartmentMinimalFactory.create_batch(20)
        for item in elastic_apartments:
            item.save()
        sleep(3)
        yield elastic_apartments
    except SkipTest:
        skip()
