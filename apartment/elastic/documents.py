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


class ApartmentDocument(ReadOnlyDocument):
    project_id = Long(required=True)
    project_uuid = Keyword(required=True)

    project_ownership_type = Keyword(required=True)
    project_housing_company = Keyword(required=True)
    project_holding_type = Keyword(required=True)
    project_street_address = Keyword(required=True)
    project_postal_code = Keyword(required=True)
    project_city = Keyword(required=True)
    project_district = Keyword(required=True)
    project_realty_id = Keyword(required=True)
    project_construction_year = Keyword()
    project_new_development_status = Keyword(required=True)
    project_new_housing = Boolean(required=True)
    project_apartment_count = Long(required=True)
    project_parkingplace_count = Long()

    project_has_elevator = Boolean()
    project_has_sauna = Boolean()
    project_construction_materials = Keyword(multi=True)
    project_roof_material = Keyword()
    project_heating_options = Keyword(multi=True)
    project_energy_class = Keyword()
    project_site_area = Float()
    project_site_owner = Keyword()
    project_site_renter = Keyword()
    project_sanitation = Keyword()
    project_zoning_info = Keyword()
    project_zoning_status = Keyword()

    project_building_type = Keyword()
    project_description = Keyword()
    project_accessibility = Keyword()
    project_smoke_free = Keyword()

    project_publication_start_time = Date()
    project_publication_end_time = Date()
    project_premarketing_start_time = Date()
    project_premarketing_end_time = Date()
    project_application_start_time = Date()
    project_application_end_time = Date()
    project_material_choice_dl = Date()
    project_shareholder_meeting_date = Date()
    project_estimated_completion = Keyword(required=True)
    project_estimated_completion_date = Date()
    project_completion_date = Date()
    project_posession_transfer_date = Date()

    project_attachment_urls = Keyword(multi=True)
    project_main_image_url = Keyword()
    project_image_urls = Keyword(multi=True)
    project_virtual_presentation_url = Keyword()

    project_acc_salesperson = Keyword()
    project_acc_financeofficer = Keyword()
    project_project_manager = Keyword()
    project_constructor = Keyword()
    project_housing_manager = Keyword()
    project_estate_agent = Keyword()
    project_estate_agent_email = Keyword()
    project_estate_agent_phone = Keyword()

    project_coordinate_lat = Float()
    project_coordinate_lon = Float()

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
    floor_plan_image = Keyword()
    image_urls = Keyword(multi=True)

    class Index:
        name = settings.APARTMENT_INDEX_NAME
