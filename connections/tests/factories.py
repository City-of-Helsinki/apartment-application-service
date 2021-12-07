import string
import uuid
from factory import Faker, fuzzy
from typing import List

from apartment.tests.factories import ApartmentDocumentTest, ElasticFactory, get_uuid
from connections.enums import ApartmentStateOfSale, ProjectStateOfSale
from connections.oikotie.field_mapper import NEW_DEVELOPMENT_STATUS_MAPPING


class ApartmentMinimalFactory(ElasticFactory):
    class Meta:
        model = ApartmentDocumentTest

    _language = fuzzy.FuzzyChoice(["en", "fi"])
    project_id = fuzzy.FuzzyInteger(0, 999)
    # mandatory fields for vendors:
    project_uuid = str(uuid.uuid4())
    uuid = fuzzy.FuzzyAttribute(get_uuid)
    project_ownership_type = fuzzy.FuzzyChoice(["Haso", "Hitas", "Puolihitas"])
    project_housing_company = fuzzy.FuzzyText()
    project_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
    project_street_address = fuzzy.FuzzyText()
    project_postal_code = fuzzy.FuzzyText(length=6, chars=string.digits)
    project_city = "Helsinki"
    project_building_type = "BLOCK_OF_FLATS"
    project_estate_agent = fuzzy.FuzzyText()
    project_estate_agent_email = Faker("email")
    apartment_number = fuzzy.FuzzyText(
        length=3, chars=string.ascii_letters + string.digits
    )

    # optional fields for vendors
    project_district = fuzzy.FuzzyText()
    project_realty_id = fuzzy.FuzzyText()
    project_new_development_status = fuzzy.FuzzyChoice(
        NEW_DEVELOPMENT_STATUS_MAPPING.keys()
    )
    project_new_housing = True
    project_apartment_count = fuzzy.FuzzyInteger(0, 999)
    project_estimated_completion = fuzzy.FuzzyText()
    room_count = fuzzy.FuzzyInteger(0, 99)
    sales_price = fuzzy.FuzzyInteger(0, 999)
    debt_free_sales_price = fuzzy.FuzzyInteger(0, 999)
    project_state_of_sale = fuzzy.FuzzyChoice(ProjectStateOfSale)
    apartment_state_of_sale = fuzzy.FuzzyChoice(ApartmentStateOfSale)
    project_description = fuzzy.FuzzyText(length=200)
    url = fuzzy.FuzzyText(length=20)
    publish_on_etuovi = Faker("boolean")
    publish_on_oikotie = Faker("boolean")

    @classmethod
    def create_batch_with_flags_published_and_state_of_sale(
        cls,
        size: int,
        for_sale=False,
        published_on_etuovi=False,
        published_on_oikotie=False,
    ) -> List[ApartmentDocumentTest]:
        if for_sale:
            for_sale = ApartmentStateOfSale.FOR_SALE
        else:
            for_sale = ApartmentStateOfSale.RESERVED
        return [
            cls.create(
                publish_on_etuovi=published_on_etuovi,
                publish_on_oikotie=published_on_oikotie,
                apartment_state_of_sale=for_sale,
                _language="fi",
            )
            for i in range(size)
        ]

    @classmethod
    def create_for_sale_batch(cls, size: int) -> List[ApartmentDocumentTest]:
        return [
            cls.create(
                publish_on_etuovi=True,
                publish_on_oikotie=True,
                apartment_state_of_sale="FOR_SALE",
                _language="fi",
            )
            for _ in range(size)
        ]
