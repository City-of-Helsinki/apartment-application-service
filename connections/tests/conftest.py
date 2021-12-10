import os
import shutil
from django.conf import settings
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection, get_connection
from pytest import fixture, skip
from rest_framework.test import APIClient

from connections.enums import ApartmentStateOfSale
from connections.tests.factories import ApartmentMinimalFactory


@fixture()
def not_sending_oikotie_ftp(monkeypatch):
    from django_oikotie import oikotie

    def send_items(path, file):
        pass

    monkeypatch.setattr(oikotie, "send_items", send_items)


@fixture()
def not_sending_etuovi_ftp(monkeypatch):
    from django_etuovi import etuovi

    def send_items(path, file):
        pass

    monkeypatch.setattr(etuovi, "send_items", send_items)


@fixture
def api_client():
    api_client = APIClient()
    return api_client


@fixture(scope="class")
def client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
    except SkipTest:
        skip()


@fixture(scope="class")
def elastic_apartments():
    connection = get_connection()
    connection.indices.delete("test-*", ignore=404)
    for_sale_none = (
        ApartmentMinimalFactory.create_batch_with_flags_published_and_state_of_sale(3)
    )
    for_sale_all = (
        ApartmentMinimalFactory.create_batch_with_flags_published_and_state_of_sale(
            3, for_sale=True, published_on_etuovi=True, published_on_oikotie=True
        )
    )
    for_sale_oikotie = (
        ApartmentMinimalFactory.create_batch_with_flags_published_and_state_of_sale(
            3, for_sale=True, published_on_oikotie=True
        )
    )
    for_sale_etuovi = (
        ApartmentMinimalFactory.create_batch_with_flags_published_and_state_of_sale(
            3, for_sale=True, published_on_etuovi=True
        )
    )
    only_for_sale = (
        ApartmentMinimalFactory.create_batch_with_flags_published_and_state_of_sale(
            3, for_sale=True
        )
    )

    elastic_apartments = (
        for_sale_none
        + for_sale_all
        + for_sale_oikotie
        + for_sale_etuovi
        + only_for_sale
    )

    yield elastic_apartments


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
        publish_on_etuovi=True,
        publish_on_oikotie=False,
    )
    # should fail with oikotie housing companies
    elastic_apartment_2 = ApartmentMinimalFactory.build(
        project_estate_agent_email="",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
        publish_on_etuovi=False,
        publish_on_oikotie=True,
    )
    # should fail with oikotie apartments and housing companies
    elastic_apartment_3 = ApartmentMinimalFactory.build(
        project_new_development_status="some text",
        project_estate_agent_email="",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
        publish_on_etuovi=False,
        publish_on_oikotie=True,
    )

    apartments = [
        elastic_apartment_1,
        elastic_apartment_2,
        elastic_apartment_3,
    ]
    for item in apartments:
        item.save(refresh="wait_for")
    yield apartments

    for item in apartments:
        item.delete(refresh="wait_for")
