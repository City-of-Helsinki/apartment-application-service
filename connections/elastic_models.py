from django.conf import settings
from elasticsearch_dsl import Boolean, Date, Document, Float, Keyword, Long


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
    project_id = Long(required=True)
    project_uuid = Keyword(required=True)

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
    apartment_count = Long(required=True)
    parkingplace_count = Long()

    has_elevator = Boolean()
    has_sauna = Boolean()
    construction_materials = Keyword(multi=True)
    roof_material = Keyword()
    heating_options = Keyword(multi=True)
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
    premarketing_end_time = Date()
    application_start_time = Date()
    application_end_time = Date()
    material_choice_dl = Date()
    shareholder_meeting_date = Date()
    estimated_completion = Keyword(required=True)
    estimated_completion_date = Date()
    completion_date = Date()
    posession_transfer_date = Date()

    attachment_urls = Keyword(multi=True)
    main_image_url = Keyword()
    image_urls = Keyword(multi=True)
    virtual_presentation_url = Keyword()

    acc_salesperson = Keyword()
    acc_financeofficer = Keyword()
    project_manager = Keyword()
    constructor = Keyword()
    housing_manager = Keyword()
    estate_agent = Keyword()
    estate_agent_email = Keyword()
    estate_agent_phone = Keyword()

    coordinate_lat = Float()
    coordinate_lon = Float()

    uuid = Keyword(required=True)

    apartment_address = Keyword()
    apartment_number = Keyword()
    housing_shares = Keyword()
    living_area = Float()
    floor = Long()
    floor_max = Long()
    showing_times = Date(multi=True)
    apartment_structure = Keyword()
    room_count = Long()
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
    parking_fee_explanation = Keyword()
    other_fees = Keyword()
    services_description = Keyword()
    additional_information = Keyword()
    application_url = Keyword()

    class Index:
        name = settings.APARTMENT_INDEX_NAME
