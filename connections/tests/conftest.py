import os
import shutil

from django.conf import settings
from pytest import fixture
from rest_framework.test import APIClient

import connections
from apartment.tests.factories import (
    add_to_store,
    APARTMENT_STORE,
    clear_apartment_store,
)
from apartment.tests.utils import TestDrupalSearchClient
from connections.enums import ApartmentStateOfSale
from connections.tests.factories import ApartmentMinimalFactory


@fixture
def not_sending_oikotie_ftp(monkeypatch):
    from django_oikotie import oikotie

    def send_items(path, file):
        pass

    monkeypatch.setattr(oikotie, "send_items", send_items)


@fixture
def not_sending_etuovi_ftp(monkeypatch):
    from django_etuovi import etuovi

    def send_items(path, file):
        pass

    monkeypatch.setattr(etuovi, "send_items", send_items)


@fixture
def api_client():
    api_client = APIClient()
    return api_client


@fixture
def elasticsearch():
    clear_apartment_store()
    yield None
    clear_apartment_store()


@fixture
def elastic_apartments(elasticsearch):
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
    add_to_store(elastic_apartments)

    yield elastic_apartments


def _mock_fetch_all(path: str, params: dict):
    client = TestDrupalSearchClient()

    return [
        hit["_source"]
        for hit in client.get(path, params=params).get("hits", {}).get("hits", [])
    ]


@fixture(autouse=True)
def mock_apartment_queries(monkeypatch):
    from apartment.elastic import queries

    monkeypatch.setattr(queries, "_fetch_all", _mock_fetch_all)


@fixture
def validate_against_schema_true(monkeypatch):
    """
    Patch `django_oikotie.utils.validate_against_schema()` to return `True`.

    CI/CD runner can't be given the secret schema URLs.
    This means it can't validate XMLs.

    Do note that this only patches it when its being imported in
    `connections.oikotie.services`. Not the smartest solution but it works for
    the current use cases.
    """
    # raise Exception("validate_against_schema_true raised this")
    monkeypatch.setattr(
        connections.oikotie.services, "validate_against_schema", lambda x, y: True
    )


@fixture
def validate_against_schema_false(monkeypatch):
    """
    Patch `django_oikotie.utils.validate_against_schema()` to return `False`.
    """

    monkeypatch.setattr(
        connections.oikotie.services, "validate_against_schema", lambda x, y: False
    )


@fixture(scope="session", autouse=True)
def test_folder():
    settings.APARTMENT_DATA_TRANSFER_PATH = "connections/tests/temp_files"
    temp_file = settings.APARTMENT_DATA_TRANSFER_PATH
    if not os.path.exists(temp_file):
        os.mkdir(temp_file)
    yield temp_file
    shutil.rmtree(temp_file)


@fixture
def invalid_data_elastic_apartments_for_sale(elastic_apartments):
    # etuovi (and oikotie apartment) invalid data is in project_holding_type
    # oikotie apartment invalid data data is in project_new_development_status
    # oikotie housing company invalid data is in project_estate_agent_email

    # should fail with oikotie apartments and etuovi
    elastic_apartment_1 = ApartmentMinimalFactory.create(
        project_holding_type="some text",
        project_new_development_status="some text",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
        publish_on_etuovi=True,
        publish_on_oikotie=False,
    )
    # should fail with oikotie housing companies
    elastic_apartment_2 = ApartmentMinimalFactory.create(
        project_estate_agent_email="",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
        _language="fi",
        publish_on_etuovi=False,
        publish_on_oikotie=True,
    )
    # should fail with oikotie apartments and housing companies
    elastic_apartment_3 = ApartmentMinimalFactory.create(
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
    add_to_store(apartments)

    yield apartments


@fixture(autouse=True)
def mock_connections_apartment_search(monkeypatch):
    from connections.enums import ApartmentStateOfSale
    from connections.etuovi.etuovi_mapper import map_apartment_to_item
    from connections.oikotie.oikotie_mapper import (
        map_oikotie_apartment,
        map_oikotie_housing_company,
    )
    from connections.utils import map_document

    def _etuovi_source():
        return [
            apt
            for apt in APARTMENT_STORE
            if apt._language == "fi"
            and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
            and apt.publish_on_etuovi is True
        ]

    def _oikotie_source():
        return [
            apt
            for apt in APARTMENT_STORE
            if apt._language == "fi"
            and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
            and apt.publish_on_oikotie is True
        ]

    def _etuovi_fetch_apartments_for_sale(verbose=False):
        items = []
        for hit in _etuovi_source():
            apartment = map_document(hit, map_apartment_to_item)
            if apartment:
                items.append(apartment)
        return items

    def _oikotie_fetch_apartments_for_sale():
        apartments = []
        housing_companies = []
        for hit in _oikotie_source():
            apartment = map_document(hit, map_oikotie_apartment)
            housing = map_document(hit, map_oikotie_housing_company)
            if apartment and housing:
                apartments.append(apartment)
                housing_companies.append(housing)
        return apartments, housing_companies
