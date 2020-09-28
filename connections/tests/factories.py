import datetime
import factory
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

    housing_company = fuzzy.FuzzyText()
    holding_type = fuzzy.FuzzyText()
    street_address = fuzzy.FuzzyText()
    postal_code = fuzzy.FuzzyText()
    city = fuzzy.FuzzyText()
    district = fuzzy.FuzzyText()
    realty_id = fuzzy.FuzzyText()
    construction_year = fuzzy.FuzzyText()
    new_development_status = fuzzy.FuzzyText()
    new_housing = True
    apartment_count = fuzzy.FuzzyInteger(0, 9999999999)

    has_elevator = True
    has_sauna = True
    construction_material = fuzzy.FuzzyText()
    roof_material = fuzzy.FuzzyText()
    heating = fuzzy.FuzzyText()
    energy_class = fuzzy.FuzzyText()
    site_area = fuzzy.FuzzyDecimal(0, 9999999999)
    site_owner = fuzzy.FuzzyText()
    site_renter = fuzzy.FuzzyText()
    sanitation = fuzzy.FuzzyText()
    zoning_info = fuzzy.FuzzyText()
    zoning_status = fuzzy.FuzzyText()

    building_type = fuzzy.FuzzyText()
    project_description = fuzzy.FuzzyText()
    accessibility = fuzzy.FuzzyText()
    smoke_free = fuzzy.FuzzyText()

    publication_start_time = fuzzy.FuzzyDate(start_date=datetime.date.today())
    publication_end_time = fuzzy.FuzzyDate(start_date=datetime.date.today())
    premarketing_start_time = fuzzy.FuzzyDate(start_date=datetime.date.today())
    application_start_time = fuzzy.FuzzyDate(start_date=datetime.date.today())
    application_end_time = fuzzy.FuzzyDate(start_date=datetime.date.today())
    material_choice_dl = fuzzy.FuzzyDate(start_date=datetime.date.today())
    shareholder_meeting_date = fuzzy.FuzzyDate(start_date=datetime.date.today())
    estimated_completion = fuzzy.FuzzyText()
    estimated_completion_date = fuzzy.FuzzyDate(start_date=datetime.date.today())
    completion_date = fuzzy.FuzzyDate(start_date=datetime.date.today())
    posession_transfer_date = fuzzy.FuzzyDate(start_date=datetime.date.today())

    attachments_url = fuzzy.FuzzyText()
    main_image = fuzzy.FuzzyText()
    virtual_presentation_url = fuzzy.FuzzyText()

    acc_salesperson = fuzzy.FuzzyText()
    acc_financeofficer = fuzzy.FuzzyText()
    project_manager = fuzzy.FuzzyText()
    constructor = fuzzy.FuzzyText()
    housing_manager = fuzzy.FuzzyText()
    estate_agent = fuzzy.FuzzyText()
    estate_agent_email = fuzzy.FuzzyText()
    estate_agent_phone = fuzzy.FuzzyText()

    coordinate_lat = fuzzy.FuzzyDecimal(0, 9999999999)
    coordinate_lon = fuzzy.FuzzyDecimal(0, 9999999999)

    apartment_address = fuzzy.FuzzyText()
    apartment_number = fuzzy.FuzzyText()
    living_area = fuzzy.FuzzyDecimal(0, 9999999999)
    floor = fuzzy.FuzzyInteger(0, 9999999999)
    floor_max = fuzzy.FuzzyInteger(0, 9999999999)
    showing_time = fuzzy.FuzzyDate(start_date=datetime.date.today())
    apartment_structure = fuzzy.FuzzyText()
    room_count = fuzzy.FuzzyInteger(0, 9999999999)
    condition = fuzzy.FuzzyText()
    kitchen_appliances = fuzzy.FuzzyText()
    has_yard = True
    has_terrace = True
    has_balcony = True
    balcony_description = fuzzy.FuzzyText()
    bathroom_appliances = fuzzy.FuzzyText()
    storage_description = fuzzy.FuzzyText()
    has_apartment_sauna = True
    apartment_holding_type = fuzzy.FuzzyText()
    view_description = fuzzy.FuzzyText()
    sales_price = fuzzy.FuzzyDecimal(0, 9999999999)
    debt_free_sales_price = fuzzy.FuzzyDecimal(0, 9999999999)
    loan_share = fuzzy.FuzzyDecimal(0, 9999999999)
    price_m2 = fuzzy.FuzzyDecimal(0, 9999999999)
    housing_company_fee = fuzzy.FuzzyDecimal(0, 9999999999)
    financing_fee = fuzzy.FuzzyDecimal(0, 9999999999)
    maintenance_fee = fuzzy.FuzzyDecimal(0, 9999999999)
    water_fee = fuzzy.FuzzyDecimal(0, 9999999999)
    water_fee_explanation = fuzzy.FuzzyText()
    parking_fee = fuzzy.FuzzyDecimal(0, 9999999999)
    other_fees = fuzzy.FuzzyText()
    services_description = fuzzy.FuzzyText()
    additional_information = fuzzy.FuzzyText()
    application_url = fuzzy.FuzzyText()
