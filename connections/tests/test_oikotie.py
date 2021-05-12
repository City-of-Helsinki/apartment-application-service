import os
import pytest
from django.conf import settings
from django.core.management import call_command
from django_etuovi.utils.testing import check_dataclass_typing
from unittest import mock

from connections.models import MappedApartment
from connections.oikotie.oikotie_mapper import (
    map_address,
    map_apartment,
    map_apartment_pictures,
    map_balcony,
    map_car_parking_charge,
    map_city,
    map_coordinates,
    map_financing_fee,
    map_floor_location,
    map_lift,
    map_living_area,
    map_maintenance_fee,
    map_mode_of_habitation,
    map_oikotie_apartment,
    map_oikotie_housing_company,
    map_real_estate_agent,
    map_sales_price,
    map_sauna,
    map_site_area,
    map_unencumbered_sales_price,
    map_water_fee,
    map_year_of_building,
)
from connections.oikotie.services import (
    create_xml_apartment_file,
    create_xml_housing_company_file,
    fetch_apartments_for_sale,
)
from connections.tests.factories import ApartmentFactory, ApartmentMinimalFactory
from connections.tests.utils import (
    get_elastic_apartments_for_sale_project_uuids,
    get_elastic_apartments_for_sale_uuids,
    make_apartments_sold_in_elastic,
)


class TestOikotieMapper:
    def test_elastic_to_oikotie_apartment_mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_apartment = map_oikotie_apartment(elastic_apartment)
        check_dataclass_typing(oikotie_apartment)

    def test_elastic_to_oikotie__apartment_minimal__mapping_types(self):
        elastic_apartment = ApartmentMinimalFactory()
        oikotie_apartment = map_oikotie_apartment(elastic_apartment)
        check_dataclass_typing(oikotie_apartment)

    def test_elastic_to_oikotie__housing_company__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_housing_company = map_oikotie_housing_company(elastic_apartment)
        check_dataclass_typing(oikotie_housing_company)

    def test_elastic_to_oikotie__address__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_address = map_address(elastic_apartment)
        check_dataclass_typing(oikotie_address)

    def test_elastic_to_oikotie__balcony__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_balcony = map_balcony(elastic_apartment)
        check_dataclass_typing(oikotie_balcony)

    def test_elastic_to_oikotie__car_parking_charge__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_car_parking_charge = map_car_parking_charge(elastic_apartment)
        check_dataclass_typing(oikotie_car_parking_charge)

    def test_elastic_to_oikotie__city__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_city = map_city(elastic_apartment)
        check_dataclass_typing(oikotie_city)

    def test_elastic_to_oikotie__coordinates__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_coordinates = map_coordinates(elastic_apartment)
        check_dataclass_typing(oikotie_coordinates)

    def test_elastic_to_oikotie__financing_fee__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_financing_fee = map_financing_fee(elastic_apartment)
        check_dataclass_typing(oikotie_financing_fee)

    def test_elastic_to_oikotie__floor_location__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_floor_location = map_floor_location(elastic_apartment)
        check_dataclass_typing(oikotie_floor_location)

    def test_elastic_to_oikotie__housing_company_apartment__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_housing_company_apartment = map_apartment(elastic_apartment)
        check_dataclass_typing(oikotie_housing_company_apartment)

    def test_elastic_to_oikotie__lift__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_lift = map_lift(elastic_apartment)
        check_dataclass_typing(oikotie_lift)

    def test_elastic_to_oikotie__living_area__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_living_area = map_living_area(elastic_apartment)
        check_dataclass_typing(oikotie_living_area)

    def test_elastic_to_oikotie__maintenance_fee__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_maintenance_fee = map_maintenance_fee(elastic_apartment)
        check_dataclass_typing(oikotie_maintenance_fee)

    def test_elastic_to_oikotie__mode_of_habitation__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_mode_of_habitation = map_mode_of_habitation(elastic_apartment)
        check_dataclass_typing(oikotie_mode_of_habitation)

    def test_elastic_to_oikotie__pictures__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_pictures = map_apartment_pictures(elastic_apartment)
        check_dataclass_typing(oikotie_pictures[0])

    def test_elastic_to_oikotie__real_estate_agent__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_real_estate_agent = map_real_estate_agent(elastic_apartment)
        check_dataclass_typing(oikotie_real_estate_agent)

    def test_elastic_to_oikotie__sales_price__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_sales_price = map_sales_price(elastic_apartment)
        check_dataclass_typing(oikotie_sales_price)

    def test_elastic_to_oikotie__sauna__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_sauna = map_sauna(elastic_apartment)
        check_dataclass_typing(oikotie_sauna)

    def test_elastic_to_oikotie__site_area__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_site_area = map_site_area(elastic_apartment)
        check_dataclass_typing(oikotie_site_area)

    def test_elastic_to_oikotie__unencumbered_sales_price__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_unencumbered_sales_price = map_unencumbered_sales_price(
            elastic_apartment
        )
        check_dataclass_typing(oikotie_unencumbered_sales_price)

    def test_elastic_to_oikotie__water_fee__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_water_fee = map_water_fee(elastic_apartment)
        check_dataclass_typing(oikotie_water_fee)

    def test_elastic_to_oikotie__year_of_building__mapping_types(self):
        elastic_apartment = ApartmentFactory()
        oikotie_year_of_building = map_year_of_building(elastic_apartment)
        check_dataclass_typing(oikotie_year_of_building)

    def test_elastic_to_oikotie_missing__apartment__project_building_type(self):
        elastic_apartment = ApartmentMinimalFactory(project_building_type=None)
        try:
            map_oikotie_apartment(elastic_apartment)
        except ValueError as e:
            assert "project_building_type" in str(e)
            return
        raise Exception("Missing project_building_type should have thrown a ValueError")

    def test_elastic_to_oikotie_missing__apartment__project_holding_type(self):
        elastic_apartment = ApartmentMinimalFactory(project_holding_type=None)
        try:
            map_oikotie_apartment(elastic_apartment)
        except ValueError as e:
            assert "project_holding_type" in str(e)
            return
        raise Exception("Missing project_holding_type should have thrown a ValueError")

    def test_elastic_to_oikotie_missing__apartment__project_city(self):
        elastic_apartment = ApartmentMinimalFactory(project_city=None)
        try:
            map_oikotie_apartment(elastic_apartment)
        except ValueError as e:
            assert "project_city" in str(e)
            return
        raise Exception("Missing project_city should have thrown a ValueError")

    def test_elastic_to_oikotie_missing__housing_company__project_city(self):
        elastic_apartment = ApartmentMinimalFactory(project_city=None)
        try:
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_city" in str(e)
            return
        raise Exception("Missing project_city should have thrown a ValueError")

    def test_elastic_to_oikotie_missing__housing_company__project_estate_agent_email(
        self,
    ):
        elastic_apartment = ApartmentMinimalFactory(project_estate_agent_email=None)
        try:
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_estate_agent_email" in str(e)
            return
        raise Exception(
            "Missing project_estate_agent_email should have thrown a ValueError"
        )

    def test_elastic_to_oikotie_missing__housing_company__project_street_address(self):
        elastic_apartment = ApartmentMinimalFactory(project_street_address=None)
        try:
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_street_address" in str(e)
            return
        raise Exception(
            "Missing project_street_address should have thrown a ValueError"
        )

    def test_elastic_to_oikotie_missing__housing_company__project_postal_code(self):
        elastic_apartment = ApartmentMinimalFactory(project_postal_code=None)
        try:
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_postal_code" in str(e)
            return
        raise Exception("Missing project_postal_code should have thrown a ValueError")


@pytest.mark.usefixtures("client", "elastic_apartments")
@mock.patch.dict(os.environ, {"ENV": "dev"}, clear=True)
@pytest.mark.django_db
class TestApartmentFetchingFromElasticAndMapping:
    """
    Tests for fetching apartments from elasticsearch with Oikotie mapper, creating XML
    files and saving correctly mapped apartments to database.
    """

    def test_apartments_for_sale_fetched_to_XML(self):
        expected_ap = get_elastic_apartments_for_sale_uuids()
        expected_hc = get_elastic_apartments_for_sale_project_uuids()

        apartments, housing_companies = fetch_apartments_for_sale()

        fetched_apartments = [item.key for item in apartments]
        fetched_housings = [item.key for item in housing_companies]

        assert expected_ap == fetched_apartments
        assert expected_hc == fetched_housings

        ap_path, ap_file_name = create_xml_apartment_file(apartments)
        hc_path, hc_file_name = create_xml_housing_company_file(housing_companies)

        assert ap_path == hc_path
        assert "APT" + settings.OIKOTIE_COMPANY_NAME in os.path.join(
            ap_path, ap_file_name
        )
        assert "HOUSINGCOMPANY" + settings.OIKOTIE_COMPANY_NAME in os.path.join(
            hc_path, hc_file_name
        )

    def test_apartments_for_sale_fetched_correctly(
        self, invalid_data_elastic_apartments_for_sale
    ):
        # Test data contains three apartments with oikotie invalid data

        expected_ap = get_elastic_apartments_for_sale_uuids()
        apartments, h_companies = fetch_apartments_for_sale()
        assert len(expected_ap) - 3 == len(apartments)

    def test_mapped_oikotie_saved_to_database(self):
        # Test data contains three apartments with oikotie invalid data
        call_command("send_oikotie_xml_file")
        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()
        expected = len(get_elastic_apartments_for_sale_uuids())

        assert oikotie_mapped == expected - 3

        etuovi_mapped = MappedApartment.objects.filter(mapped_etuovi=True).count()

        assert etuovi_mapped == 0

    def test_no_apartments_for_sale(self):
        make_apartments_sold_in_elastic()
        apartments, housing_companies = fetch_apartments_for_sale()

        assert len(apartments) == 0
        assert len(housing_companies) == 0

        _, ap_file_name = create_xml_apartment_file(apartments)
        _, hc_file_name = create_xml_housing_company_file(housing_companies)

        assert ap_file_name is None
        assert hc_file_name is None
