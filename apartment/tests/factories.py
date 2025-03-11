import string
from datetime import date, timedelta

import factory
from django.conf import settings
from django.utils import timezone
from elasticsearch_dsl import Document
from factory import Faker, fuzzy

from apartment.elastic.documents import ApartmentDocument

datetime_string_format = "%Y-%m-%dT%H:%M:%S%z"


class ApartmentDocumentTest(ApartmentDocument):
    def save(self, **kwargs):
        return Document.save(self, **kwargs)

    def update(self, **fields):
        return Document.update(self, **fields)

    def delete(self, **kwargs):
        return Document.delete(self, **kwargs)

    class Index:
        name = settings.TEST_APARTMENT_INDEX_NAME


class ElasticFactory(factory.Factory):
    @factory.post_generation
    def save_to_elastic(obj, create, extracted, **kwargs):
        if not create:
            return
        obj.save(refresh="true")


class ApartmentDocumentFactory(ElasticFactory):
    class Meta:
        model = ApartmentDocumentTest

    _language = fuzzy.FuzzyChoice(["en", "fi", "sv"])
    project_id = fuzzy.FuzzyInteger(0, 999)
    project_uuid = factory.Faker("uuid4")

    project_ownership_type = fuzzy.FuzzyChoice(["Haso", "Hitas", "Puolihitas"])
    project_housing_company = fuzzy.FuzzyText()
    project_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
    project_street_address = fuzzy.FuzzyText()
    project_postal_code = fuzzy.FuzzyText(length=6, chars=string.digits)
    project_city = "Helsinki"
    project_district = fuzzy.FuzzyText()
    project_realty_id = fuzzy.FuzzyText()
    project_construction_year = fuzzy.FuzzyInteger(2000, 3000)
    project_new_development_status = fuzzy.FuzzyChoice(
        ["UNDER_PLANNING", "PRE_MARKETING", "UNDER_CONSTRUCTION", "READY_TO_MOVE"]
    )
    project_new_housing = True
    project_apartment_count = fuzzy.FuzzyInteger(0, 999)
    project_parkingplace_count = fuzzy.FuzzyInteger(0, 999)
    project_state_of_sale = fuzzy.FuzzyChoice(
        ["PRE_MARKETING", "FOR_SALE", "PROCESSING", "READY"]
    )

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
    project_description = fuzzy.FuzzyText(length=200)
    url = fuzzy.FuzzyText(length=20)
    project_accessibility = fuzzy.FuzzyText()
    project_smoke_free = fuzzy.FuzzyText()

    project_publication_start_time = (
        fuzzy.FuzzyDateTime(timezone.now()).fuzz().strftime(datetime_string_format)
    )
    project_publication_end_time = (
        fuzzy.FuzzyDateTime(timezone.now()).fuzz().strftime(datetime_string_format)
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
    project_estate_agent_email = Faker("email")
    project_estate_agent_phone = fuzzy.FuzzyText()

    project_coordinate_lat = fuzzy.FuzzyFloat(-90, 90)
    project_coordinate_lon = fuzzy.FuzzyFloat(-180, 180)

    apartment_state_of_sale = fuzzy.FuzzyChoice(
        [
            "FOR_SALE",
            "OPEN_FOR_APPLICATIONS",
            "FREE_FOR_RESERVATIONS",
            "RESERVED",
            "SOLD",
        ]
    )

    uuid = factory.Faker("uuid4")

    apartment_address = fuzzy.FuzzyText()
    apartment_number = fuzzy.FuzzyText(
        length=3, chars=string.ascii_letters + string.digits
    )
    housing_shares = fuzzy.FuzzyText()
    living_area = fuzzy.FuzzyFloat(0, 9999999999)
    floor = fuzzy.FuzzyInteger(0, 999)
    floor_max = fuzzy.FuzzyInteger(0, 999)
    showing_times = factory.List(
        [
            fuzzy.FuzzyDateTime(timezone.now()).fuzz().strftime(datetime_string_format)
            for _ in range(2)
        ]
    )
    apartment_structure = fuzzy.FuzzyText()
    room_count = fuzzy.FuzzyInteger(0, 999)
    condition = "Uusi"
    kitchen_appliances = fuzzy.FuzzyText()
    has_yard = True
    has_balcony = True
    balcony_description = fuzzy.FuzzyText()
    bathroom_appliances = fuzzy.FuzzyText()
    storage_description = fuzzy.FuzzyText()
    has_apartment_sauna = True
    apartment_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
    view_description = fuzzy.FuzzyText()
    sales_price = fuzzy.FuzzyInteger(0, 999)
    debt_free_sales_price = fuzzy.FuzzyInteger(0, 999)
    loan_share = fuzzy.FuzzyInteger(0, 999)
    price_m2 = fuzzy.FuzzyInteger(0, 999)
    housing_company_fee = fuzzy.FuzzyInteger(0, 999)
    financing_fee = fuzzy.FuzzyInteger(0, 999)
    financing_fee_m2 = fuzzy.FuzzyInteger(0, 999)
    maintenance_fee = fuzzy.FuzzyInteger(0, 999)
    maintenance_fee_m2 = fuzzy.FuzzyInteger(0, 999)
    water_fee = fuzzy.FuzzyInteger(0, 999)
    water_fee_explanation = fuzzy.FuzzyText()
    parking_fee = fuzzy.FuzzyInteger(0, 999)
    parking_fee_explanation = fuzzy.FuzzyText()
    other_fees = fuzzy.FuzzyText()
    services_description = fuzzy.FuzzyText()
    additional_information = fuzzy.FuzzyText()
    application_url = fuzzy.FuzzyText()
    image_urls = factory.List([fuzzy.FuzzyText() for _ in range(2)])
    publish_on_etuovi = Faker("boolean")
    publish_on_oikotie = Faker("boolean")
    right_of_occupancy_payment = fuzzy.FuzzyInteger(0, 999)
    right_of_occupancy_fee = fuzzy.FuzzyInteger(0, 999)
    project_contract_apartment_completion_selection_1 = Faker("boolean")
    project_contract_apartment_completion_selection_1_date = fuzzy.FuzzyDate(
        start_date=timezone.localdate() - timedelta(days=7),
        end_date=timezone.localdate() - timedelta(days=1),
    )
    project_contract_apartment_completion_selection_2 = Faker("boolean")
    project_contract_apartment_completion_selection_2_start = fuzzy.FuzzyDate(
        start_date=timezone.localdate() - timedelta(days=7),
        end_date=timezone.localdate() - timedelta(days=1),
    )
    project_contract_apartment_completion_selection_2_end = fuzzy.FuzzyDate(
        start_date=timezone.localdate() + timedelta(days=1),
        end_date=timezone.localdate() + timedelta(days=7),
    )
    project_contract_apartment_completion_selection_3 = Faker("boolean")
    project_contract_apartment_completion_selection_3_date = fuzzy.FuzzyDate(
        start_date=timezone.localdate() - timedelta(days=7),
        end_date=timezone.localdate() - timedelta(days=1),
    )
    project_contract_depositary = fuzzy.FuzzyText()
    project_contract_estimated_handover_date_start = fuzzy.FuzzyDate(
        start_date=timezone.localdate() - timedelta(days=7),
        end_date=timezone.localdate() - timedelta(days=1),
    )
    project_contract_estimated_handover_date_end = fuzzy.FuzzyDate(
        start_date=timezone.localdate() + timedelta(days=1),
        end_date=timezone.localdate() + timedelta(days=7),
    )
    project_contract_customer_document_handover = fuzzy.FuzzyText()
    project_contract_bill_of_sale_terms = fuzzy.FuzzyText()
    project_contract_material_selection_date = fuzzy.FuzzyDate(
        start_date=timezone.localdate() - timedelta(days=7),
        end_date=timezone.localdate() - timedelta(days=1),
    )
    project_contract_material_selection_description = fuzzy.FuzzyText()
    project_contract_material_selection_later = Faker("boolean")
    project_contract_other_terms = fuzzy.FuzzyText()
    project_contract_usage_fees = fuzzy.FuzzyText()
    project_contract_repository = fuzzy.FuzzyText()
    project_contract_right_of_occupancy_payment_verification = fuzzy.FuzzyText()
    project_property_number = fuzzy.FuzzyText(length=3)
    project_contract_rs_bank = fuzzy.FuzzyText()

    project_contract_collateral_type = fuzzy.FuzzyText()
    project_contract_default_collateral = fuzzy.FuzzyText()
    project_contract_construction_permit_requested = fuzzy.FuzzyDate(
        start_date=timezone.localdate() - timedelta(days=7),
        end_date=timezone.localdate() - timedelta(days=1),
    )
    project_documents_delivered = fuzzy.FuzzyText()
