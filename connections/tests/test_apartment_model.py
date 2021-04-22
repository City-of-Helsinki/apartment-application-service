import pytest
from datetime import date

from connections.tests.factories import ApartmentFactory, ApartmentTest


@pytest.mark.usefixtures("client")
class TestApartmentModel:
    def test_apartment_index_has_data(client):
        apartment = ApartmentFactory(_id=42)
        apartment.save()

        at = ApartmentTest.get(id=42)

        fields = ApartmentTest._doc_type.mapping.properties.properties
        for field in fields:
            input_value = getattr(apartment, field)
            index_value = getattr(at, field)
            if type(input_value) == date:
                # elasticsearch-dsl does not support plain date values in the index.
                # If 2020-01-01 is saved to the index,
                # it will return 2020-01-01 00:00:00.
                index_value = index_value.date()
            assert input_value == index_value
