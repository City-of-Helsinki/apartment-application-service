from django_etuovi.utils.testing import check_dataclass_typing

from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.tests.factories import ApartmentFactory, ApartmentMinimalFactory


def test__apartment__to_item_mapping_types():
    apartment = ApartmentFactory()
    item = map_apartment_to_item(apartment)
    check_dataclass_typing(item)


def test__apartment_minimal__to_item_mapping_types():
    apartment = ApartmentMinimalFactory()
    item = map_apartment_to_item(apartment)
    check_dataclass_typing(item)


def test_elastic_to_etuovi_missing_apartment__project_holding_type():
    elastic_apartment = ApartmentMinimalFactory(project_holding_type=None)
    try:
        map_apartment_to_item(elastic_apartment)
    except ValueError as e:
        assert "project_holding_type" in str(e)
        return
    raise Exception("Missing project_holding_type should have thrown a ValueError")


def test_elastic_to_etuovi_missing_apartment__project_building_type():
    elastic_apartment = ApartmentMinimalFactory(project_building_type=None)
    try:
        map_apartment_to_item(elastic_apartment)
    except ValueError as e:
        assert "project_building_type" in str(e)
        return
    raise Exception("Missing project_building_type should have thrown a ValueError")
