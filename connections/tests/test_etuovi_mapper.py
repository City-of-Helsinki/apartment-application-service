from django_etuovi.utils.testing import check_dataclass_typing

from connections.etuovi.mapper import map_apartment_to_item
from connections.tests.factories import ApartmentFactory


def test_apartment_to_item_mapping_types():
    apartment = ApartmentFactory()
    item = map_apartment_to_item(apartment)
    check_dataclass_typing(item)
