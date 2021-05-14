import os
import shutil
from django.conf import settings
from django.contrib.auth.models import Permission
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection
from pytest import fixture, skip
from rest_framework.test import APIClient
from time import sleep

from application_form.tests.factories import UserFactory
from connections.enums import ApartmentStateOfSale
from connections.tests.factories import ApartmentMinimalFactory


@fixture(autouse=True)
def use_test_elasticsearch_envs(settings):
    settings.ELASTICSEARCH_PORT = os.environ.get("ELASTICSEARCH_HOST_PORT", 9200)
    settings.ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_HOST", "localhost")


@fixture()
def not_sending_oikotie_ftp(monkeypatch):
    from django_oikotie import oikotie

    def send_items(file):
        pass

    monkeypatch.setattr(oikotie, "send_items", send_items)


@fixture()
def not_sending_etuovi_ftp(monkeypatch):
    from django_etuovi import etuovi

    def send_items(file):
        pass

    monkeypatch.setattr(etuovi, "send_items", send_items)


@fixture
def api_client():
    user = UserFactory()
    permissions = Permission.objects.all()
    user.user_permissions.set(permissions)
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


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
    sale_apartments = []
    while not sale_apartments:
        elastic_apartments = ApartmentMinimalFactory.create_batch(20)
        sale_apartments = [
            item.apartment_state_of_sale == "FOR_SALE" and item._language == "fi"
            for item in elastic_apartments
        ]
    try:
        for item in elastic_apartments:
            item.save()
        sleep(3)
        yield elastic_apartments
    except SkipTest:
        skip()


@fixture(scope="session", autouse=True)
def test_folder():
    settings.APARTMENT_DATA_TRANSFER_PATH = "connections/tests/temp_files"
    temp_file = settings.APARTMENT_DATA_TRANSFER_PATH
    if not os.path.exists(temp_file):
        os.mkdir(temp_file)
    yield temp_file
    shutil.rmtree(temp_file)


@fixture()
def invalid_data_elastic_apartments_for_sale():
    # etuovi (and oikotie apartment) invalid data is in project_holding_type
    # oikotie apartment invalid data data is in project_new_development_status
    # oikotie housing company invalid data is in project_estate_agent_email

    # should fail with oikotie apartments and etuovi
    elastic_apartment_1 = ApartmentMinimalFactory.build(
        project_holding_type="some text",
        project_new_development_status="some text",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
    )
    # should fail with oikotie housing companies
    elastic_apartment_2 = ApartmentMinimalFactory.build(
        project_estate_agent_email="",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
    )
    # should fail with oikotie apartments and housing companies
    elastic_apartment_3 = ApartmentMinimalFactory.build(
        project_new_development_status="some text",
        project_estate_agent_email="",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
    )

    for item in [
        elastic_apartment_1,
        elastic_apartment_2,
        elastic_apartment_3,
    ]:
        item.save()
    sleep(3)
    yield elastic_apartments
