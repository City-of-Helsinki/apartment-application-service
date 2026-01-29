from apartment.tests.factories import ApartmentDocumentFactory


class TestApartmentModel:
    def test_apartment_factory_has_fields(self):
        apartment = ApartmentDocumentFactory()

        for field in (
            "uuid",
            "project_uuid",
            "project_housing_company",
            "apartment_address",
            "apartment_number",
        ):
            assert getattr(apartment, field)
