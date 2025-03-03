import os
from uuid import UUID

import pytest
from django.conf import settings
from django.core.management import call_command
from django_etuovi.utils.testing import check_dataclass_typing

from apartment.tests.factories import ApartmentDocumentFactory
from connections.models import MappedApartment
from connections.oikotie.oikotie_mapper import (
    form_description,
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
from connections.tests.factories import ApartmentMinimalFactory
from connections.tests.utils import (
    get_elastic_apartments_for_sale_project_uuids,
    get_elastic_apartments_for_sale_published_on_etuovi_uuids,
    get_elastic_apartments_for_sale_published_on_oikotie_uuids,
    make_apartments_sold_in_elastic,
    publish_elastic_apartments,
    unpublish_elastic_oikotie_apartments,
)


class TestOikotieMapper:
    def test_elastic_to_oikotie_apartment_mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_apartment = map_oikotie_apartment(elastic_apartment)
        check_dataclass_typing(oikotie_apartment)

    def test_elastic_to_oikotie__apartment_minimal__mapping_types(self):
        elastic_apartment = ApartmentMinimalFactory()
        oikotie_apartment = map_oikotie_apartment(elastic_apartment)
        check_dataclass_typing(oikotie_apartment)

    def test_elastic_to_oikotie__housing_company__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_housing_company = map_oikotie_housing_company(elastic_apartment)
        check_dataclass_typing(oikotie_housing_company)

    def test_elastic_to_oikotie__address__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_address = map_address(elastic_apartment)
        check_dataclass_typing(oikotie_address)

    def test_elastic_to_oikotie__balcony__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_balcony = map_balcony(elastic_apartment)
        check_dataclass_typing(oikotie_balcony)

    def test_elastic_to_oikotie__car_parking_charge__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_car_parking_charge = map_car_parking_charge(elastic_apartment)
        check_dataclass_typing(oikotie_car_parking_charge)

    def test_elastic_to_oikotie__city__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_city = map_city(elastic_apartment)
        check_dataclass_typing(oikotie_city)

    def test_elastic_to_oikotie__coordinates__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_coordinates = map_coordinates(elastic_apartment)
        check_dataclass_typing(oikotie_coordinates)

    def test_elastic_to_oikotie__financing_fee__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_financing_fee = map_financing_fee(elastic_apartment)
        check_dataclass_typing(oikotie_financing_fee)

    def test_elastic_to_oikotie__floor_location__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_floor_location = map_floor_location(elastic_apartment)
        check_dataclass_typing(oikotie_floor_location)

    def test_elastic_to_oikotie__housing_company_apartment__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_housing_company_apartment = map_apartment(elastic_apartment)
        check_dataclass_typing(oikotie_housing_company_apartment)

    def test_elastic_to_oikotie__lift__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_lift = map_lift(elastic_apartment)
        check_dataclass_typing(oikotie_lift)

    def test_elastic_to_oikotie__living_area__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_living_area = map_living_area(elastic_apartment)
        check_dataclass_typing(oikotie_living_area)

    def test_elastic_to_oikotie__maintenance_fee__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_maintenance_fee = map_maintenance_fee(elastic_apartment)
        check_dataclass_typing(oikotie_maintenance_fee)

    def test_elastic_to_oikotie__mode_of_habitation__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_mode_of_habitation = map_mode_of_habitation(elastic_apartment)
        check_dataclass_typing(oikotie_mode_of_habitation)

    def test_elastic_to_oikotie__pictures__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_pictures = map_apartment_pictures(elastic_apartment)
        check_dataclass_typing(oikotie_pictures[0])

    def test_elastic_to_oikotie__real_estate_agent__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_real_estate_agent = map_real_estate_agent(elastic_apartment)
        check_dataclass_typing(oikotie_real_estate_agent)

    def test_elastic_to_oikotie__sales_price__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_sales_price = map_sales_price(elastic_apartment)
        check_dataclass_typing(oikotie_sales_price)

    def test_elastic_to_oikotie__sauna__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_sauna = map_sauna(elastic_apartment)
        check_dataclass_typing(oikotie_sauna)

    def test_elastic_to_oikotie__site_area__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_site_area = map_site_area(elastic_apartment)
        check_dataclass_typing(oikotie_site_area)

    def test_elastic_to_oikotie__unencumbered_sales_price__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_unencumbered_sales_price = map_unencumbered_sales_price(
            elastic_apartment
        )
        check_dataclass_typing(oikotie_unencumbered_sales_price)

    def test_elastic_to_oikotie__water_fee__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
        oikotie_water_fee = map_water_fee(elastic_apartment)
        check_dataclass_typing(oikotie_water_fee)

    def test_elastic_to_oikotie__year_of_building__mapping_types(self):
        elastic_apartment = ApartmentDocumentFactory()
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
        try:
            elastic_apartment = ApartmentMinimalFactory(project_holding_type=None)
            map_oikotie_apartment(elastic_apartment)
        except ValueError as e:
            assert "project_holding_type" in str(e)
            return
        raise Exception("Missing project_holding_type should have thrown a ValueError")

    def test_elastic_to_oikotie_missing__apartment__project_city(self):
        try:
            elastic_apartment = ApartmentMinimalFactory(project_city=None)
            map_oikotie_apartment(elastic_apartment)
        except ValueError as e:
            assert "project_city" in str(e)
            return
        raise Exception("Missing project_city should have thrown a ValueError")

    def test_elastic_to_oikotie_missing__housing_company(self):
        try:
            elastic_apartment = ApartmentMinimalFactory(project_housing_company=None)
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_housing_company" in str(e)
            return
        raise Exception(
            "Missing project_housing_company should have thrown a ValueError"
        )

    def test_elastic_to_oikotie_missing__housing_company__project_city(self):
        try:
            elastic_apartment = ApartmentMinimalFactory(project_city=None)
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
        try:
            elastic_apartment = ApartmentMinimalFactory(project_street_address=None)
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_street_address" in str(e)
            return
        raise Exception(
            "Missing project_street_address should have thrown a ValueError"
        )

    def test_elastic_to_oikotie_missing__housing_company__project_postal_code(self):
        try:
            elastic_apartment = ApartmentMinimalFactory(project_postal_code=None)
            map_oikotie_housing_company(elastic_apartment)
        except ValueError as e:
            assert "project_postal_code" in str(e)
            return
        raise Exception("Missing project_postal_code should have thrown a ValueError")

    @pytest.mark.parametrize(
        "description,link,expected",
        [
            (
                "full description",
                "link_to_project",
                "full description\n\nlink_to_project",
            ),
            (
                None,
                "link_to_project",
                "Tarkemman kohde-esittelyn sekä varaustilanteen löydät täältä:"
                + "\nlink_to_project",
            ),
            (
                "full description",
                None,
                "full description",
            ),
        ],
    )
    def test_elastic_to_oikotie_missing__project_description(
        self, description, link, expected
    ):
        elastic_apartment = ApartmentMinimalFactory(
            project_description=description, url=link
        )
        formed_description = form_description(elastic_apartment)

        assert formed_description.strip() == expected.strip()


@pytest.mark.django_db
@pytest.mark.usefixtures("client")
class TestApartmentFetchingFromElasticAndMapping:
    """
    Tests for fetching apartments from elasticsearch with Oikotie mapper, creating XML
    files and saving correctly mapped apartments to database.
    """

    @pytest.mark.usefixtures("elastic_apartments", "validate_against_schema_true")
    def test_apartments_for_sale_fetched_to_XML(self):
        expected_ap = get_elastic_apartments_for_sale_published_on_oikotie_uuids()
        expected_hc = get_elastic_apartments_for_sale_project_uuids()

        apartments, housing_companies = fetch_apartments_for_sale()

        fetched_apartments = [item.key for item in apartments]
        fetched_housings = [item.key for item in housing_companies]

        assert expected_ap == fetched_apartments
        assert expected_hc == fetched_housings

        ap_file_name = create_xml_apartment_file(apartments)
        hc_file_name = create_xml_housing_company_file(housing_companies)

        assert "APT" + settings.OIKOTIE_COMPANY_NAME in os.path.join(
            settings.APARTMENT_DATA_TRANSFER_PATH, ap_file_name
        )
        assert "HOUSINGCOMPANY" + settings.OIKOTIE_COMPANY_NAME in os.path.join(
            settings.APARTMENT_DATA_TRANSFER_PATH, hc_file_name
        )

    def test_apartments_for_sale_mapped_correctly(
        self, invalid_data_elastic_apartments_for_sale
    ):
        # Test data contains three apartments with oikotie invalid data

        elastic_oikotie_ap = (
            get_elastic_apartments_for_sale_published_on_oikotie_uuids()
        )
        expected_ap = elastic_oikotie_ap.copy()

        # remove invalid data
        for i in invalid_data_elastic_apartments_for_sale:
            if i.publish_on_oikotie is True:
                expected_ap.remove(i.uuid)

        apartments, _ = fetch_apartments_for_sale()
        apartments = [i.key for i in apartments]

        assert elastic_oikotie_ap != apartments
        assert expected_ap == apartments

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "elastic_apartments", "validate_against_schema_true"
    )
    def test_mapped_oikotie_saved_to_database_with_publish_updated(self):
        call_command("send_oikotie_xml_file")
        oikotie_mapped = MappedApartment.objects.filter(
            mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)

        expected = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_oikotie_uuids())
        )

        assert sorted(oikotie_mapped) == sorted(expected)

        etuovi_mapped = MappedApartment.objects.filter(mapped_etuovi=True).count()

        assert etuovi_mapped == 0

        # get not published oikotie apartments
        not_published = get_elastic_apartments_for_sale_published_on_etuovi_uuids(
            only_etuovi_published=True
        )
        expected_new = list(
            map(
                UUID, publish_elastic_apartments(not_published, publish_to_oikotie=True)
            )
        )

        call_command("send_oikotie_xml_file")
        oikotie_mapped_new = MappedApartment.objects.filter(
            mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)

        assert oikotie_mapped_new != oikotie_mapped
        # new apartments are 3 from only etuovi published
        assert oikotie_mapped_new.count() - oikotie_mapped.count() == 3
        assert sorted(expected_new) == sorted(oikotie_mapped_new)

        etuovi_mapped = MappedApartment.objects.filter(mapped_etuovi=True).count()

        assert etuovi_mapped == 0

        # return data to original
        unpublish_elastic_oikotie_apartments(not_published)

    @pytest.mark.usefixtures("elastic_apartments", "validate_against_schema_true")
    def test_no_apartments_for_sale(self):
        """
        Test that after apartments are sold database is updated and
        no files are created
        """
        call_command("send_oikotie_xml_file")
        expected = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_oikotie_uuids())
        )

        make_apartments_sold_in_elastic()
        apartments, housing_companies = fetch_apartments_for_sale()

        call_command("send_oikotie_xml_file")
        oikotie_not_mapped = MappedApartment.objects.filter(
            mapped_oikotie=False
        ).values_list("apartment_uuid", flat=True)

        assert len(apartments) == 0
        assert len(housing_companies) == 0
        assert sorted(oikotie_not_mapped) == sorted(expected)

        ap_file_name = create_xml_apartment_file(apartments)
        hc_file_name = create_xml_housing_company_file(housing_companies)

        assert ap_file_name is None
        assert hc_file_name is None


@pytest.mark.django_db
@pytest.mark.usefixtures("client")
class TestSendOikotieXMLFileCommand:
    """
    Tests for django command send_oikotie_xml_file with different parameters
    """

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "elastic_apartments", "validate_against_schema_true"
    )
    def test_send_oikotie_xml_file_only_create_files(self, test_folder):
        """
        Test that after calling send_oikotie_xml_file --only_create_files
        files are created but no database entries are made
        """

        call_command("send_oikotie_xml_file", "--only_create_files")
        files = os.listdir(test_folder)

        assert any("APT" + settings.OIKOTIE_COMPANY_NAME in f for f in files)
        assert any("HOUSINGCOMPANY" + settings.OIKOTIE_COMPANY_NAME in f for f in files)

        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()

        assert oikotie_mapped == 0

        for f in files:
            os.remove(os.path.join(test_folder, f))

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "elastic_apartments", "validate_against_schema_true"
    )
    def test_send_oikotie_xml_file_send_only_type_1(self, test_folder):
        """
        Test that after calling send_oikotie_xml_file --send_only_type 1
        housing company file is created but database entries are not made.
        """
        call_command("send_oikotie_xml_file", "--send_only_type", 1)
        files = os.listdir(test_folder)

        assert any("HOUSINGCOMPANY" + settings.OIKOTIE_COMPANY_NAME in f for f in files)

        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()

        assert oikotie_mapped == 0

        for f in files:
            os.remove(os.path.join(test_folder, f))

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "elastic_apartments", "validate_against_schema_true"
    )
    def test_send_oikotie_xml_file_send_only_type_2(self, test_folder):
        """
        Test that after calling send_oikotie_xml_file --send_only_type 2
        apartment file is created and no database entries are made.
        Test that after adding more oikotie apartments to publish and running command
        again database is updated.
        """
        call_command("send_oikotie_xml_file", "--send_only_type", 2)
        files = os.listdir(test_folder)

        assert any("APT" + settings.OIKOTIE_COMPANY_NAME in f for f in files)

        oikotie_mapped = MappedApartment.objects.filter(
            mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)

        expected = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_oikotie_uuids())
        )

        assert len(expected) == 6
        assert sorted(oikotie_mapped) == sorted(expected)

        not_published = get_elastic_apartments_for_sale_published_on_etuovi_uuids(
            only_etuovi_published=True
        )
        # adds 3 new apartment not published before on oikotie
        publish_elastic_apartments(not_published, publish_to_oikotie=True)

        call_command("send_oikotie_xml_file", "--send_only_type", 2)

        oikotie_mapped_new = MappedApartment.objects.filter(
            mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)

        expected_new = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_oikotie_uuids())
        )

        assert sorted(oikotie_mapped_new) == sorted(expected_new)
        assert len(expected_new) > len(expected)

        # return data to original
        unpublish_elastic_oikotie_apartments(not_published)

        for f in files:
            os.remove(os.path.join(test_folder, f))

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "elastic_apartments", "validate_against_schema_true"
    )
    def test_send_oikotie_xml_no_arguments(self, test_folder):
        """
        Test that after calling send_oikotie_xml_file without arguments
        files are created and database entries are made
        """
        call_command("send_oikotie_xml_file")
        files = os.listdir(test_folder)

        assert any("APT" + settings.OIKOTIE_COMPANY_NAME in f for f in files)
        assert any("HOUSINGCOMPANY" + settings.OIKOTIE_COMPANY_NAME in f for f in files)

        oikotie_mapped = MappedApartment.objects.filter(
            mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)

        expected = list(
            map(UUID, get_elastic_apartments_for_sale_published_on_oikotie_uuids())
        )

        assert sorted(oikotie_mapped) == sorted(expected)

        for f in files:
            os.remove(os.path.join(test_folder, f))

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "elastic_apartments", "validate_against_schema_true"
    )
    def test_send_oikotie_xml_no_apartments(self, test_folder):
        """
        Test that after calling send_oikotie_xml_file with no apartments to map,
        no files are created and no database entries are made
        """
        make_apartments_sold_in_elastic()

        call_command("send_oikotie_xml_file")
        files = os.listdir(test_folder)

        assert not files

        oikotie_mapped = MappedApartment.objects.filter(mapped_oikotie=True).count()

        assert oikotie_mapped == 0
