from django.conf import settings
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection
from pytest import fixture, skip


@fixture(autouse=True)
def use_oikotie_vendor_id():
    settings.OIKOTIE_VENDOR_ID = "A1234"


@fixture(scope="session")
def client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
        connection.indices.delete("test-*", ignore=404)
    except SkipTest:
        skip()
