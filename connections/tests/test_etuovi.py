import os
from uuid import UUID

import pytest
from django.conf import settings
from django.core.management import call_command
from django_etuovi.utils.testing import check_dataclass_typing

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.etuovi.services import create_xml, fetch_apartments_for_sale
from connections.models import MappedApartment
from connections.tests.factories import ApartmentMinimalFactory
from connections.tests.utils import (
    get_elastic_apartments_for_sale_published_on_etuovi_uuids,
    get_elastic_apartments_for_sale_published_on_oikotie_uuids,
    make_apartments_sold_in_elastic,
    publish_elastic_apartments,
)
from connections.utils import a_tags_to_text


class TestEtuoviMapper:
    @pytest.mark.parametrize(
        "ownership_type", [OwnershipType.HASO, OwnershipType.HITAS]
    )
    def test_apartment_to_item_mapping_types(self, ownership_type):
        apartment = ApartmentDocumentFactory(
            project_ownership_type=ownership_type.value
        )
        item = map_apartment_to_item(apartment)
        check_dataclass_typing(item)

    def test_apartment_minimal_to_item_mapping_types(self):
        apartment = ApartmentMinimalFactory()
        item = map_apartment_to_item(apartment)
        check_dataclass_typing(item)

    def test_elastic_to_etuovi_missing_apartment_project_holding_type(self):
        try:
            elastic_apartment = ApartmentMinimalFactory(project_holding_type=None)
            map_apartment_to_item(elastic_apartment)
        except ValueError as e:
            assert "project_holding_type" in str(e)
            return
        raise Exception("Missing project_holding_type should have thrown a ValueError")

    def test_elastic_to_etuovi_missing_apartment_project_building_type(self):
        elastic_apartment = ApartmentMinimalFactory(project_building_type=None)
        try:
            map_apartment_to_item(elastic_apartment)
        except ValueError as e:
            assert "project_building_type" in str(e)
            return
        raise Exception("Missing project_building_type should have thrown a ValueError")


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
class TestApartmentFetchingFromElasticAndMapping:
    """
    Tests for fetching apartments from elasticsearch with Etuovi mapper, creating XML
    file and saving correctly mapped apartments to database.
    """

    @pytest.mark.usefixtures("elastic_apartments")
    def test_apartments_for_sale_fetched_to_XML(self):
        expected = get_elastic_apartments_for_sale_published_on_etuovi_uuids()
        items = fetch_apartments_for_sale()
        fetched = [item.cust_itemcode for item in items]

        assert expected == fetched

        file_name = create_xml(items)

        assert settings.ETUOVI_COMPANY_NAME in os.path.join(
            settings.APARTMENT_DATA_TRANSFER_PATH, file_name
        )

    def test_apartments_for_sale_fetched_correctly(
        self, invalid_data_elastic_apartments_for_sale
    ):
        # Test data contains one apartment with etuovi invalid data
        elastic_etuovi = get_elastic_apartments_for_sale_published_on_etuovi_uuids()
        expected = elastic_etuovi.copy()

        # remove invalid data
        for i in invalid_data_elastic_apartments_for_sale:
            if i.publish_on_etuovi is True:
                expected.remove(i.uuid)

        apartments = [i.cust_itemcode for i in fetch_apartments_for_sale()]

        assert elastic_etuovi != apartments
        assert expected == apartments

    @pytest.mark.usefixtures("not_sending_etuovi_ftp", "elastic_apartments")
    def test_mapped_etuovi_saved_to_database_with_publish_updated(self):
        call_command("send_etuovi_xml_file")
        etuovi_mapped = MappedApartment.objects.filter(mapped_etuovi=True).values_list(
            "apartment_uuid", flat=True
        )
        expected = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_etuovi_uuids())
        )

        assert sorted(etuovi_mapped) == sorted(expected)

        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()

        assert oikotie_mapped == 0

        # get not published etuovi apartments
        not_published = get_elastic_apartments_for_sale_published_on_oikotie_uuids(
            only_oikotie_published=True
        )

        expected_new = list(
            map(UUID, publish_elastic_apartments(not_published, publish_to_etuovi=True))
        )

        call_command("send_etuovi_xml_file")
        etuovi_mapped_new = MappedApartment.objects.filter(
            mapped_etuovi=True
        ).values_list("apartment_uuid", flat=True)

        assert etuovi_mapped_new != etuovi_mapped
        # new apartments are 3 from only oikotie published
        assert etuovi_mapped_new.count() - etuovi_mapped.count() == 3
        assert sorted(expected_new) == sorted(etuovi_mapped_new)

        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()

        assert oikotie_mapped == 0

    @pytest.mark.usefixtures("elastic_apartments")
    def test_no_apartments_for_sale_not_creating_file_and_updating_database(self):
        call_command("send_etuovi_xml_file")
        expected = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_etuovi_uuids())
        )

        make_apartments_sold_in_elastic()
        items = fetch_apartments_for_sale()

        call_command("send_etuovi_xml_file")
        etuovi_not_mapped = MappedApartment.objects.filter(
            mapped_etuovi=False
        ).values_list("apartment_uuid", flat=True)

        assert len(items) == 0
        assert sorted(etuovi_not_mapped) == sorted(expected)

        file_name = create_xml(items)

        assert file_name is None

    def test_etuovi_map_energy_class_default_value(self):
        """Energy class should be validated. Etuovi only allows certain strings.
        Apartments with no energy class get `None` as the value"""
        apartment_no_energy_class = ApartmentMinimalFactory(project_energy_class=None)

        apartment_with_valid_energy_class = ApartmentMinimalFactory(
            project_energy_class="A2007"
        )

        apartment_with_invalid_energy_class = ApartmentMinimalFactory(
            project_energy_class="non-existant class string"
        )

        mapped_apartment_with_valid_energy_class = map_apartment_to_item(
            apartment_with_valid_energy_class
        )
        mapped_apartment_no_energy_class = map_apartment_to_item(
            apartment_no_energy_class
        )
        mapped_apartment_with_invalid_energy_class = map_apartment_to_item(
            apartment_with_invalid_energy_class
        )

        assert mapped_apartment_with_valid_energy_class.energyclass == "A2007"
        assert mapped_apartment_no_energy_class.energyclass is None
        assert mapped_apartment_with_invalid_energy_class.energyclass is None

    def test_strip_link_tags(self):
        input_text = """<p>Lorem ipsum <a href='https://foo.bar'>FooBar link</a></p><p><a href='mailto:user.name@mail.com'>user.name@mail.com</a><a href='https://test.site'>Test site over here</a><a href='https://test.site/gallery'>Image gallery is here</a></p>"""  # noqa: E501

        expected_text = '<p>Lorem ipsum <p>\nFooBar link\nhttps://foo.bar\n</p></p><p><a href="mailto:user.name@mail.com">user.name@mail.com</a><p>\nTest site over here\nhttps://test.site\n</p><p>\nImage gallery is here\nhttps://test.site/gallery\n</p></p>'  # noqa: E501

        text_no_link_tags = a_tags_to_text(input_text)
        assert text_no_link_tags == expected_text
        pass
