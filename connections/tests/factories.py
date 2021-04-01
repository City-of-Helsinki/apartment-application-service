from datetime import date
import factory
import uuid
from django.utils import timezone
from elasticsearch_dsl import Document
from factory import fuzzy

from connections.elastic_models import Apartment


class ApartmentTest(Apartment):
    def save(self, **kwargs):
        return Document.save(self, **kwargs)

    def update(self, **fields):
        return Document.update(self, **fields)

    def delete(self, **kwargs):
        return Document.delete(self, **kwargs)

    class Index:
        name = "test-apartment"


class ApartmentFactory(factory.Factory):
    class Meta:
        model = ApartmentTest

    project_id = fuzzy.FuzzyInteger(0, 9999999999)
    project_uuid = str(uuid.uuid4())

    project_housing_company = fuzzy.FuzzyText()
    project_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
    project_street_address = fuzzy.FuzzyText()
    project_postal_code = fuzzy.FuzzyText()
    project_city = "Helsinki"
    project_district = fuzzy.FuzzyText()
    project_realty_id = fuzzy.FuzzyText()
    project_construction_year = fuzzy.FuzzyInteger(2000, 3000)
    project_new_development_status = fuzzy.FuzzyText()
    project_new_housing = True
    project_apartment_count = fuzzy.FuzzyInteger(0, 9999999999)
    project_parkingplace_count = fuzzy.FuzzyInteger(0, 9999999999)

    project_has_elevator = True
    project_has_sauna = True
    project_construction_materials = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    project_roof_material = fuzzy.FuzzyText()
    project_heating_options = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    project_energy_class = fuzzy.FuzzyText()
    project_site_area = fuzzy.FuzzyFloat(0, 9999999999)
    project_site_owner = fuzzy.FuzzyChoice(["Oma", "Vuokra"])
    project_site_renter = fuzzy.FuzzyText()
    project_sanitation = fuzzy.FuzzyText()
    project_zoning_info = fuzzy.FuzzyText()
    project_zoning_status = fuzzy.FuzzyText()

    project_building_type = "BLOCK_OF_FLATS"
    project_description = fuzzy.FuzzyText()
    project_accessibility = fuzzy.FuzzyText()
    project_smoke_free = fuzzy.FuzzyText()

    project_publication_start_time = (
        fuzzy.FuzzyDateTime(timezone.now()).fuzz().strftime("%Y-%m-%dT%H:%M:%S%z")
    )
    project_publication_end_time = (
        fuzzy.FuzzyDateTime(timezone.now()).fuzz().strftime("%Y-%m-%dT%H:%M:%S%z")
    )
    project_premarketing_start_time = fuzzy.FuzzyDateTime(timezone.now())
    project_premarketing_end_time = fuzzy.FuzzyDateTime(timezone.now())
    project_application_start_time = fuzzy.FuzzyDateTime(timezone.now())
    project_application_end_time = fuzzy.FuzzyDateTime(timezone.now())
    project_material_choice_dl = fuzzy.FuzzyDate(date.today())
    project_shareholder_meeting_date = fuzzy.FuzzyDate(date.today())
    project_estimated_completion = fuzzy.FuzzyText()
    project_estimated_completion_date = fuzzy.FuzzyDate(date.today())
    project_completion_date = fuzzy.FuzzyDate(date.today())
    project_posession_transfer_date = fuzzy.FuzzyDate(date.today())

    project_attachment_urls = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    project_main_image_url = fuzzy.FuzzyText()
    project_image_urls = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    project_virtual_presentation_url = fuzzy.FuzzyText()

    project_acc_salesperson = fuzzy.FuzzyText()
    project_acc_financeofficer = fuzzy.FuzzyText()
    project_project_manager = fuzzy.FuzzyText()
    project_constructor = fuzzy.FuzzyText()
    project_housing_manager = fuzzy.FuzzyText()
    project_estate_agent = fuzzy.FuzzyText()
    project_estate_agent_email = fuzzy.FuzzyText()
    project_estate_agent_phone = fuzzy.FuzzyText()

    project_coordinate_lat = fuzzy.FuzzyFloat(-90, 90)
    project_coordinate_lon = fuzzy.FuzzyFloat(-180, 180)

    uuid = str(uuid.uuid4())

    apartment_address = fuzzy.FuzzyText()
    apartment_number = fuzzy.FuzzyText()
    housing_shares = fuzzy.FuzzyText()
    living_area = fuzzy.FuzzyFloat(0, 9999999999)
    floor = fuzzy.FuzzyInteger(0, 9999999999)
    floor_max = fuzzy.FuzzyInteger(0, 9999999999)
    showing_times = factory.List(
        [
            fuzzy.FuzzyDateTime(timezone.now()).fuzz().strftime("%Y-%m-%dT%H:%M:%S%z")
            for _ in range(2)
        ]
    )
    apartment_structure = fuzzy.FuzzyText()
    room_count = fuzzy.FuzzyInteger(0, 9999999999)
    condition = "Uusi"
    kitchen_appliances = fuzzy.FuzzyText()
    has_yard = True
    has_terrace = True
    has_balcony = True
    balcony_description = fuzzy.FuzzyText()
    bathroom_appliances = fuzzy.FuzzyText()
    storage_description = fuzzy.FuzzyText()
    has_apartment_sauna = True
    apartment_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
    view_description = fuzzy.FuzzyText()
    sales_price = fuzzy.FuzzyInteger(0, 9999999999)
    debt_free_sales_price = fuzzy.FuzzyInteger(0, 9999999999)
    loan_share = fuzzy.FuzzyInteger(0, 9999999999)
    price_m2 = fuzzy.FuzzyInteger(0, 9999999999)
    housing_company_fee = fuzzy.FuzzyInteger(0, 9999999999)
    financing_fee = fuzzy.FuzzyInteger(0, 9999999999)
    financing_fee_m2 = fuzzy.FuzzyInteger(0, 9999999999)
    maintenance_fee = fuzzy.FuzzyInteger(0, 9999999999)
    maintenance_fee_m2 = fuzzy.FuzzyInteger(0, 9999999999)
    water_fee = fuzzy.FuzzyInteger(0, 9999999999)
    water_fee_explanation = fuzzy.FuzzyText()
    parking_fee = fuzzy.FuzzyInteger(0, 9999999999)
    parking_fee_explanation = fuzzy.FuzzyText()
    other_fees = fuzzy.FuzzyText()
    services_description = fuzzy.FuzzyText()
    additional_information = fuzzy.FuzzyText()
    application_url = fuzzy.FuzzyText()
    image_urls = factory.List([fuzzy.FuzzyText() for _ in range(2)])


class ApartmentMinimalFactory(factory.Factory):
    class Meta:
        model = ApartmentTest

    project_id = fuzzy.FuzzyInteger(0, 9999999999)
    project_uuid = str(uuid.uuid4())

    project_housing_company = fuzzy.FuzzyText()
    project_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
    project_street_address = fuzzy.FuzzyText()
    project_postal_code = fuzzy.FuzzyText()
    project_city = "Helsinki"
    project_district = fuzzy.FuzzyText()
    project_realty_id = fuzzy.FuzzyText()
    project_new_development_status = fuzzy.FuzzyText()
    project_new_housing = True
    project_apartment_count = fuzzy.FuzzyInteger(0, 9999999999)
    project_estimated_completion = fuzzy.FuzzyText()
    project_estate_agent_email = fuzzy.FuzzyText()

    project_building_type = "BLOCK_OF_FLATS"

    uuid = str(uuid.uuid4())

    room_count = fuzzy.FuzzyInteger(0, 9999999999)
    sales_price = fuzzy.FuzzyInteger(0, 9999999999)
    debt_free_sales_price = fuzzy.FuzzyInteger(0, 9999999999)
