import typing

from connections.etuovi.mapper import map_apartment_to_item
from connections.tests.factories import ApartmentFactory


def test_apartment_to_item_mapping_types():
    apartment = ApartmentFactory()
    item = map_apartment_to_item(apartment)

    for field_name, field_def in item.__dataclass_fields__.items():
        actual_type = typing.get_origin(field_def.type) or field_def.type
        actual_value = getattr(item, field_name)
        assert isinstance(actual_value, actual_type)
