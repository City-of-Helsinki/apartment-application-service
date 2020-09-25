from connections.tests.factories import ApartmentFactory, ApartmentTest


def test_apartment_has_required_fields(client):
    apartment = ApartmentFactory(_id=42)
    apartment.save()

    at = ApartmentTest.get(id=42)

    assert at.housing_company == apartment.housing_company
    assert at.holding_type == apartment.holding_type
    assert at.street_address == apartment.street_address
    assert at.postal_code == apartment.postal_code
    assert at.city == apartment.city
    assert at.district == apartment.district
    assert at.realty_id == apartment.realty_id
    assert at.construction_year == apartment.construction_year
    assert at.new_development_status == apartment.new_development_status
    assert at.new_housing == apartment.new_housing
    assert at.apartment_count == apartment.apartment_count
    assert at.estimated_completion == apartment.estimated_completion
