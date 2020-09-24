from django.conf import settings
from elasticsearch_dsl import Boolean, Date, Document, Integer, Keyword, Long


class ReadOnlyDocument(Document):
    @classmethod
    def init(cls, index=None, using=None):
        raise NotImplementedError()

    def save(self, **kwargs):
        raise NotImplementedError()

    def update(self, **fields):
        raise NotImplementedError()

    def delete(self, **kwargs):
        raise NotImplementedError()


class Apartment(ReadOnlyDocument):
    housing_company = Keyword(required=True)
    holding_type = Keyword(required=True)
    street_address = Keyword(required=True)
    postal_code = Keyword(required=True)
    city = Keyword(required=True)
    district = Keyword(required=True)
    realty_id = Keyword(required=True)
    construction_year = Keyword()
    new_development_status = Keyword(required=True)
    new_housing = Boolean(required=True)
    apartment_count = Integer(required=True)

    has_elevator = Boolean()
    has_sauna = Boolean()
    construction_material = Keyword()
    roof_material = Keyword()
    heating = Keyword()
    energy_class = Keyword()
    site_area = Long()
    site_owner = Keyword()
    site_renter = Keyword()
    sanitation = Keyword()
    zoning_info = Keyword()
    zoning_status = Keyword()

    building_type = Keyword()
    project_description = Keyword()
    accessibility = Keyword()
    smoke_free = Keyword()

    publication_start_time = Date()
    publication_end_time = Date()
    premarketing_start_time = Date()
    application_start_time = Date()
    application_end_time = Date()
    material_choice_dl = Date()
    shareholder_meeting_date = Date()
    estimated_completion = Keyword(required=True)
    estimated_completion_date = Date()
    completion_date = Date()
    posession_transfer_date = Date()

    attachments_url = Keyword()
    main_image = Keyword()
    virtual_presentation_url = Keyword()

    acc_salesperson = Keyword()
    acc_financeofficer = Keyword()
    project_manager = Keyword()
    constructor = Keyword()
    housing_manager = Keyword()
    estate_agent = Keyword()
    estate_agent_email = Keyword()
    estate_agent_phone = Keyword()

    coordinate_lat = Long()
    coordinate_lon = Long()

    apartment_address = Keyword()
    apartment_number = Keyword()
    living_area = Long()
    floor = Integer()
    floor_max = Integer()
    showing_time = Date()
    apartment_structure = Keyword()
    room_count = Integer()
    condition = Keyword()
    kitchen_appliances = Keyword()
    has_yard = Boolean()
    has_terrace = Boolean()
    has_balcony = Boolean()
    balcony_description = Keyword()
    bathroom_appliances = Keyword()
    storage_description = Keyword()
    has_apartment_sauna = Boolean()
    apartment_holding_type = Keyword()
    view_description = Keyword()
    sales_price = Long()
    debt_free_sales_price = Long()
    loan_share = Long()
    price_m2 = Long()
    housing_company_fee = Long()
    financing_fee = Long()
    maintenance_fee = Long()
    water_fee = Long()
    water_fee_explanation = Keyword()
    parking_fee = Long()
    other_fees = Keyword()
    services_description = Keyword()
    additional_information = Keyword()
    application_url = Keyword()

    class Index:
        name = settings.APARTMENT_INDEX_NAME
