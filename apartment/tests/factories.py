import factory
import string
from datetime import date
from django.utils import timezone
from elasticsearch_dsl import Document
from factory import Faker, fuzzy
from string import ascii_letters, digits
from typing import List

from apartment.elastic.documents import ApartmentDocument
from apartment.enums import IdentifierSchemaType
from apartment.models import Apartment, Identifier, Project

datetime_string_format = "%Y-%m-%dT%H:%M:%S%z"


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    uuid = factory.Faker("uuid4")
    street_address = Faker("street_address")

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for identifier in extracted:
                IdentifierFactory.create(
                    identifier=identifier, project=self, apartment=None
                )
        else:
            identifier = IdentifierFactory.create(project=self, apartment=None)
            self.identifiers.add(identifier)


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    street_address = Faker("street_address")
    apartment_number = fuzzy.FuzzyText(length=3, chars=ascii_letters + digits)
    project = factory.SubFactory(ProjectFactory)
    room_count = fuzzy.FuzzyInteger(1, 10)

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for identifier in extracted:
                self.identifiers.add(
                    IdentifierFactory.create(
                        identifier=identifier, apartment=self, project=None
                    )
                )

        else:
            identifier = IdentifierFactory.create(apartment=self, project=None)
            self.identifiers.add(identifier)

    @classmethod
    def create_batch_with_project(
        cls, size: int, project=None, identifier_schema="att"
    ) -> List[Apartment]:
        if project is None:
            project = cls.project
        if identifier_schema == "att":
            identifiers = [
                IdentifierFactory(
                    identifier=factory.Faker("uuid4"),
                    schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
                    apartment=None,
                    project=None,
                )
            ]

        apartments = []
        for i in range(size):
            apartment = cls.create(identifiers=identifiers, project=project)
            apartments.append(apartment)
        return apartments


class IdentifierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Identifier
        django_get_or_create = ("identifier",)

    schema_type = fuzzy.FuzzyChoice(list(IdentifierSchemaType))
    identifier = fuzzy.FuzzyText(length=36)
    project = factory.SubFactory(ProjectFactory)
    apartment = factory.SubFactory(ApartmentFactory)

    @classmethod
    def build_batch_for_att_schema(cls, size: int, uuids_list: list):
        return [
            cls.build(
                identifier=str(uuids_list[i]),
                schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
            )
            for i in range(size)
        ]


class ApartmentDocumentTest(ApartmentDocument):
    def save(self, **kwargs):
        return Document.save(self, **kwargs)

    def update(self, **fields):
        return Document.update(self, **fields)

    def delete(self, **kwargs):
        return Document.delete(self, **kwargs)

    class Index:
        name = "test-apartment"


class ElasticFactory(factory.Factory):
    @factory.post_generation
    def save_to_elastic(obj, create, extracted, **kwargs):
        if not create:
            return
        obj.save(refresh="wait_for")


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

    project_state_of_sale = fuzzy.FuzzyChoice(
        ["PRE_MARKETING", "FOR_SALE", "PROCESSING", "READY"]
    )
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
    has_terrace = True
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
