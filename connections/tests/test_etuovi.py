import os
import pytest
from django.conf import settings
from django.core.management import call_command
from django_etuovi.utils.testing import check_dataclass_typing

from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.etuovi.services import create_xml, fetch_apartments_for_sale
from connections.models import MappedApartment
from connections.tests.factories import ApartmentFactory, ApartmentMinimalFactory
from connections.tests.utils import (
    get_elastic_apartments_for_sale_uuids,
    make_apartments_sold_in_elastic,
)


class TestEtuoviMapper:
    def test_apartment_to_item_mapping_types(self):
        apartment = ApartmentFactory()
        item = map_apartment_to_item(apartment)
        check_dataclass_typing(item)

    def test_apartment_minimal_to_item_mapping_types(self):
        apartment = ApartmentMinimalFactory()
        item = map_apartment_to_item(apartment)
        check_dataclass_typing(item)

    def test_elastic_to_etuovi_missing_apartment_project_holding_type(self):
        elastic_apartment = ApartmentMinimalFactory(project_holding_type=None)
        try:
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


@pytest.mark.usefixtures("client", "elastic_apartments")
@pytest.mark.django_db
class TestApartmentFetchingFromElasticAndMapping:
    """
    Tests for fetching apartments from elasticsearch with Etuovi mapper, creating XML
    file and saving correctly mapped apartments to database.
    """

    def test_apartments_for_sale_fetched_to_XML(self):
        expected = get_elastic_apartments_for_sale_uuids()
        items = fetch_apartments_for_sale()
        fetched = [item.cust_itemcode for item in items]

        assert expected == fetched

        file_name = create_xml(items)

        assert settings.ETUOVI_COMPANY_NAME in os.path.join(
            settings.APARTMENT_DATA_TRANSFER_PATH, file_name
        )

    @pytest.mark.usefixtures("invalid_data_elastic_apartments_for_sale")
    def test_apartments_for_sale_fetched_correctly(self):
        # Test data contains one apartment with etuovi invalid data
        expected = get_elastic_apartments_for_sale_uuids()
        items = fetch_apartments_for_sale()

        assert len(expected) - 1 == len(items)

    @pytest.mark.usefixtures(
        "invalid_data_elastic_apartments_for_sale", "not_sending_etuovi_ftp"
    )
    def test_mapped_etuovi_saved_to_database(self):
        # Test data contains one apartment with etuovi invalid data
        call_command("send_etuovi_xml_file")
        etuovi_mapped = MappedApartment.objects.filter(mapped_etuovi=True).count()
        expected = len(get_elastic_apartments_for_sale_uuids())

        assert etuovi_mapped == expected - 1

        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()

        assert oikotie_mapped == 0

    def test_no_apartments_for_sale_not_creating_file_and_updating_database(self):
        call_command("send_etuovi_xml_file")
        expected = len(get_elastic_apartments_for_sale_uuids())

        make_apartments_sold_in_elastic()
        items = fetch_apartments_for_sale()

        call_command("send_etuovi_xml_file")
        etuovi_not_mapped = MappedApartment.objects.filter(mapped_etuovi=False).count()

        assert len(items) == 0
        assert etuovi_not_mapped == expected

        file_name = create_xml(items)

        assert file_name is None
