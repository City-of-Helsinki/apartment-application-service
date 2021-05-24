import pytest
from django_etuovi.utils.testing import check_dataclass_typing
from time import sleep

from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.etuovi.services import fetch_apartments_for_sale
from connections.tests.factories import ApartmentFactory, ApartmentMinimalFactory


class TestEtuoviMapper:
    def test_apartment_to_item_mapping_types(self):
        apartment = ApartmentFactory()
        item = map_apartment_to_item(apartment)
        check_dataclass_typing(item)

    def test_apartment_minimal_to_item_mapping_types(self):
        apartment = ApartmentMinimalFactory()
        item = map_apartment_to_item(apartment)
        check_dataclass_typing(item)

    def test_elastic_to_etuovi_missing_apartment_project_holding_type(self):
        elastic_apartment = ApartmentMinimalFactory(project_holding_type=None)
        try:
            map_apartment_to_item(elastic_apartment)
        except ValueError as e:
            assert "project_holding_type" in str(e)
            return
        raise Exception("Missing project_holding_type should have thrown a ValueError")

    def test_elastic_to_etuovi_missing_apartment_project_building_type(self):
        elastic_apartment = ApartmentMinimalFactory(project_building_type=None)
        try:
            map_apartment_to_item(elastic_apartment)
        except ValueError as e:
            assert "project_building_type" in str(e)
            return
        raise Exception("Missing project_building_type should have thrown a ValueError")


@pytest.mark.usefixtures("client", "elastic_apartments")
class TestApartmentFetchingFromElastic:
    def test_apartments_for_sale_fetched_correctly(self, elastic_apartments):
        expected = [
            str(item["uuid"])
            for item in elastic_apartments
            if item["apartment_state_of_sale"] == "FOR_SALE"
            and item["_language"] == "fi"
        ]

        items = fetch_apartments_for_sale()

        fetched = [item.cust_itemcode for item in items]

        assert expected == fetched

    def test_no_apartments_for_sale(self, elastic_apartments):
        for item in elastic_apartments:
            if item["apartment_state_of_sale"] == "FOR_SALE":
                item.delete()
        sleep(3)
        items = fetch_apartments_for_sale()

        assert len(items) == 0
