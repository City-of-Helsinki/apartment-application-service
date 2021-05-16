import os
import shutil
from django.conf import settings
from django.test import override_settings
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


@fixture(scope="session", autouse=True)
@override_settings(APARTMENT_DATA_TRANSFER_PATH="connections/tests/temp_files")
def test_folder():
    temp_file = settings.APARTMENT_DATA_TRANSFER_PATH
    if not os.path.exists(temp_file):
        os.mkdir(temp_file)
    yield temp_file
    shutil.rmtree(temp_file)
