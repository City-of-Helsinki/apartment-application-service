import datetime
import factory
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
    project_uuid = fuzzy.FuzzyText()

    housing_company = fuzzy.FuzzyText()
    holding_type = "Asumisoikeushuoneisto"
    street_address = fuzzy.FuzzyText()
    postal_code = fuzzy.FuzzyText()
    city = fuzzy.FuzzyText()
    district = fuzzy.FuzzyText()
    realty_id = fuzzy.FuzzyText()
    construction_year = fuzzy.FuzzyInteger(2000, 3000)
    new_development_status = fuzzy.FuzzyText()
    new_housing = True
    apartment_count = fuzzy.FuzzyInteger(0, 9999999999)
    parkingplace_count = fuzzy.FuzzyInteger(0, 9999999999)

    has_elevator = True
    has_sauna = True
    construction_materials = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    roof_material = fuzzy.FuzzyText()
    heating_options = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    energy_class = fuzzy.FuzzyText()
    site_area = fuzzy.FuzzyFloat(0, 9999999999)
    site_owner = fuzzy.FuzzyText()
    site_renter = fuzzy.FuzzyText()
    sanitation = fuzzy.FuzzyText()
    zoning_info = fuzzy.FuzzyText()
    zoning_status = fuzzy.FuzzyText()

    building_type = "Kerrostalo"
    project_description = fuzzy.FuzzyText()
    accessibility = fuzzy.FuzzyText()
    smoke_free = fuzzy.FuzzyText()

    publication_start_time = fuzzy.FuzzyDateTime(timezone.now())
    publication_end_time = fuzzy.FuzzyDateTime(timezone.now())
    premarketing_start_time = fuzzy.FuzzyDateTime(timezone.now())
    premarketing_end_time = fuzzy.FuzzyDateTime(timezone.now())
    application_start_time = fuzzy.FuzzyDateTime(timezone.now())
    application_end_time = fuzzy.FuzzyDateTime(timezone.now())
    material_choice_dl = fuzzy.FuzzyDate(datetime.date.today())
    shareholder_meeting_date = fuzzy.FuzzyDate(datetime.date.today())
    estimated_completion = fuzzy.FuzzyText()
    estimated_completion_date = fuzzy.FuzzyDate(datetime.date.today())
    completion_date = fuzzy.FuzzyDate(datetime.date.today())
    posession_transfer_date = fuzzy.FuzzyDate(datetime.date.today())

    attachment_urls = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    main_image_url = fuzzy.FuzzyText()
    image_urls = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    virtual_presentation_url = fuzzy.FuzzyText()

    acc_salesperson = fuzzy.FuzzyText()
    acc_financeofficer = fuzzy.FuzzyText()
    project_manager = fuzzy.FuzzyText()
    constructor = fuzzy.FuzzyText()
    housing_manager = fuzzy.FuzzyText()
    estate_agent = fuzzy.FuzzyText()
    estate_agent_email = fuzzy.FuzzyText()
    estate_agent_phone = fuzzy.FuzzyText()

    coordinate_lat = fuzzy.FuzzyFloat(-90, 90)
    coordinate_lon = fuzzy.FuzzyFloat(-180, 180)

    uuid = fuzzy.FuzzyText()

    apartment_address = fuzzy.FuzzyText()
    apartment_number = fuzzy.FuzzyText()
    housing_shares = fuzzy.FuzzyText()
    living_area = fuzzy.FuzzyFloat(0, 9999999999)
    floor = fuzzy.FuzzyInteger(0, 9999999999)
    floor_max = fuzzy.FuzzyInteger(0, 9999999999)
    showing_times = factory.List(
        [fuzzy.FuzzyDateTime(timezone.now()) for _ in range(2)]
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
    apartment_holding_type = "Asumisoikeushuoneisto"
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
