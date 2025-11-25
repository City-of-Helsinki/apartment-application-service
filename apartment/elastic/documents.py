from django.conf import settings
from elasticsearch_dsl import Boolean, Date, Document, Float, Keyword, Long, Text

from cost_index.utils import (
    current_right_of_occupancy_payment,
    reservation_right_of_occupancy_payment,
)


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
    project_contract_business_id = Keyword(required=True)
    project_district = Keyword(required=True)
    project_realty_id = Keyword(required=True)
    project_construction_year = Keyword()
    project_completion_date = Keyword()
    project_new_development_status = Keyword(required=True)
    project_new_housing = Boolean(required=True)
    project_apartment_count = Long(required=True)
    project_parkingplace_count = Long()
    project_state_of_sale = Keyword()

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
    project_can_apply_afterwards = Boolean()
    project_material_choice_dl = Date()
    project_shareholder_meeting_date = Date()
    project_estimated_completion = Keyword(required=True)
    project_estimated_completion_date = Date()
    project_completion_date = Date()
    project_possession_transfer_date = Date()
    project_shares_transferred_when = Keyword()
    project_control_transferred_when = Keyword()
    project_published = Boolean()
    project_archived = Boolean()

    project_attachment_urls = Keyword(multi=True)
    project_main_image_url = Keyword()
    project_image_urls = Keyword(multi=True)
    project_virtual_presentation_url = Keyword()
    project_url = Keyword()
    project_use_complete_contract = Boolean()

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

    project_barred_bank_account = Keyword()
    project_regular_bank_account = Keyword()
    project_payment_recipient = Keyword()
    project_payment_recipient_final = Keyword()

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
    title = Keyword()
    site_owner = Keyword()
    services = Keyword()
    apartment_state_of_sale = Keyword()
    apartment_published = Boolean()
    stock_start_number = Long()
    stock_end_number = Long()

    right_of_occupancy_payment = Long()
    right_of_occupancy_fee = Long()
    right_of_occupancy_deposit = Long()
    release_payment = Long()

    # These two fields are synchronized by drupal
    # from ApartmentRevaluation model
    field_index_adjusted_right_of_oc = Long()
    field_alteration_work = Long()

    project_contract_apartment_completion_selection_1 = Boolean()
    project_contract_apartment_completion_selection_1_date = Date()
    project_contract_apartment_completion_selection_2 = Boolean()
    project_contract_apartment_completion_selection_2_start = Date()
    project_contract_apartment_completion_selection_2_end = Date()
    project_contract_apartment_completion_selection_3 = Boolean()
    project_contract_apartment_completion_selection_3_date = Date()
    project_contract_depositary = Text()

    project_contract_estimated_handover_date_start = Date()
    project_contract_estimated_handover_date_end = Date()
    project_contract_customer_document_handover = Text()
    project_contract_bill_of_sale_terms = Text()
    project_contract_material_selection_date = Date()
    project_contract_material_selection_description = Text()
    project_contract_material_selection_later = Boolean()
    project_contract_other_terms = Keyword()
    project_contract_usage_fees = Keyword()
    project_contract_repository = Text()
    project_contract_right_of_occupancy_payment_verification = Keyword()
    project_contract_rs_bank = Keyword()

    project_contract_collateral_type = Text()
    project_contract_default_collateral = Text()
    project_contract_construction_permit_requested = Date()
    project_contract_article_of_association = Text()
    project_contract_transfer_restriction = Boolean()
    project_customer_document_handover = Text()
    project_documents_delivered = Text()

    class Index:
        name = settings.APARTMENT_INDEX_NAME

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        properties_to_print = []

        if self.project_uuid:
            properties_to_print += [
                "project_uuid",
                "project_housing_company",
            ]

        properties_to_print += [
            "nid", 
            "uuid",
            "apartment_address",
        ]

        properties_str = ", ".join(
            f"{prop_name}='{getattr(self, prop_name)}'" for prop_name in properties_to_print
        )
        return f"ApartmentDocument({properties_str})"

    @property
    def current_right_of_occupancy_payment(self):
        """
        Determine the effective current right of occupancy payment
        by searching for updated values in local database.
        """
        return current_right_of_occupancy_payment(
            self.uuid, self.right_of_occupancy_payment
        )

    def reservation_right_of_occupancy_payment(self, reservation_id: int):
        return reservation_right_of_occupancy_payment(
            reservation_id, self.uuid, self.right_of_occupancy_payment
        )

    @property
    def project_contract_combined_terms(self):
        items = [
            self.project_contract_bill_of_sale_terms,
            self.project_contract_other_terms,
            self.project_contract_customer_document_handover,
        ]
        non_empty_items = [x for x in items if isinstance(x, str) and x]
        return "\n\n".join(non_empty_items)
