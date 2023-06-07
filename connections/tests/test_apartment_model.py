from datetime import date

import pytest

from apartment.tests.factories import ApartmentDocumentFactory, ApartmentDocumentTest


@pytest.mark.usefixtures("client")
class TestApartmentModel:
    def test_apartment_index_has_data(client):
        apartment = ApartmentDocumentFactory(_id=42)
        apartment.save()

        at = ApartmentDocumentTest.get(id=42)

        fields = ApartmentDocumentTest._doc_type.mapping.properties.properties
        for field in fields:
            input_value = getattr(apartment, field)
            index_value = getattr(at, field)
            if type(input_value) == date:
                # elasticsearch-dsl does not support plain date values in the index.
                # If 2020-01-01 is saved to the index,
                # it will return 2020-01-01 00:00:00.
                index_value = index_value.date()
            assert input_value == index_value
