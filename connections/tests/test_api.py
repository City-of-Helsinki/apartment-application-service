import datetime

import pytest
from django.core.management import call_command
from django.urls import reverse

from connections.enums import ApartmentStateOfSale
from connections.models import MappedApartment
from connections.tests.factories import ApartmentMinimalFactory
from connections.tests.utils import (
    get_elastic_apartments_for_sale_only_uuids,
    get_elastic_apartments_for_sale_published_uuids,
    get_elastic_apartments_not_for_sale,
    make_apartments_sold_in_elastic,
    publish_elastic_apartments,
)
from users.tests.conftest import (  # noqa: F401, F811
    drupal_salesperson_api_client,
    drupal_server_api_client,
    profile_api_client,
    sales_ui_salesperson_api_client,
    user_api_client,
)


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
class TestConnectionsApis:
    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_get_mapped_apartments(
        self,
        drupal_server_api_client,  # noqa: F811
    ):
        expected = get_elastic_apartments_for_sale_published_uuids()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = drupal_server_api_client.get(
            "/v1/connections/get_mapped_apartments", follow=True
        )

        assert response.data == expected

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_get_new_published_apartments(
        self,
        drupal_server_api_client,  # noqa: F811
    ):
        expected = get_elastic_apartments_for_sale_published_uuids()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = drupal_server_api_client.get(
            "/v1/connections/get_mapped_apartments", follow=True
        )

        assert sorted(response.data) == sorted(expected)

        not_published = get_elastic_apartments_for_sale_only_uuids()
        expected_new = publish_elastic_apartments(
            not_published, publish_to_etuovi=True, publish_to_oikotie=True
        )

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response_new = drupal_server_api_client.get(
            "/v1/connections/get_mapped_apartments", follow=True
        )

        assert sorted(response_new.data) == sorted(expected_new)
        # new apartments are 3 from not published anywhere
        assert len(response_new.data) - len(response.data) == 3

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_apartments_for_sale_need_FOR_SALE_flag(
        self,
        drupal_server_api_client,  # noqa: F811
    ):
        expected = get_elastic_apartments_not_for_sale()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = drupal_server_api_client.get(
            "/v1/connections/get_mapped_apartments", follow=True
        )

        assert set(expected) not in set(response.data)

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_no_mapped_apartments(
        self,
        drupal_server_api_client,  # noqa: F811
    ):
        """
        if no apartments are mapped should return empty list
        """
        make_apartments_sold_in_elastic()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = drupal_server_api_client.get(
            "/v1/connections/get_mapped_apartments", follow=True
        )

        assert response.data == []

    @pytest.mark.django_db
    def test_get_integration_status_unauthorized(
        APIClient,
        user_api_client,  # noqa: F811
        profile_api_client,  # noqa: F811
        drupal_salesperson_api_client,  # noqa: F811
    ):
        # tests rewrite APIClient when initializing so we re-import here
        from rest_framework.test import APIClient

        api_client = APIClient()

        response = api_client.get(reverse("connections:Connections-integration-status"))
        assert response.status_code == 403

        response = user_api_client.get(
            reverse("connections:Connections-integration-status")
        )
        assert response.status_code == 403

        response = profile_api_client.get(
            reverse("connections:Connections-integration-status")
        )
        assert response.status_code == 403

        response = drupal_salesperson_api_client.get(
            reverse("connections:Connections-integration-status")
        )
        assert response.status_code == 403

    @pytest.mark.usefixtures("elastic_apartments")
    def test_get_integration_status_authorized(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that authorized request returns 200 status code"""
        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )
        assert response.status_code == 200
        assert "etuovi" in response.data
        assert "oikotie" in response.data
        assert "success" in response.data["etuovi"]
        assert "fail" in response.data["etuovi"]
        assert "success" in response.data["oikotie"]
        assert "fail" in response.data["oikotie"]

    @pytest.mark.usefixtures("elastic_apartments")
    def test_integration_status_response_structure(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that response has correct structure"""

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        data = response.data

        # Check structure
        assert isinstance(data, dict)
        assert "etuovi" in data
        assert "oikotie" in data

        for integration in ["etuovi", "oikotie"]:
            assert "success" in data[integration]
            assert "fail" in data[integration]
            assert isinstance(data[integration]["success"], list)
            assert isinstance(data[integration]["fail"], list)

            # Check fail items structure
            for fail_item in data[integration]["fail"]:
                assert "uuid" in fail_item
                assert "missing_fields" in fail_item
                assert isinstance(fail_item["missing_fields"], list)
                assert "last_mapped" in fail_item
            # Check success items structure (should match fail items structure)
            for success_item in data[integration]["success"]:
                assert "uuid" in success_item
                assert "missing_fields" in success_item
                assert isinstance(success_item["missing_fields"], list)
                assert "last_mapped" in success_item

    @pytest.mark.usefixtures("elastic_apartments", "not_sending_etuovi_ftp")
    def test_integration_status_etuovi_with_all_required_fields(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that apartments with all Etuovi required fields are in success list"""
        # Create apartment with all Etuovi required fields
        apartment = ApartmentMinimalFactory.create(
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_etuovi=True,
            _language="fi",
            # All Etuovi required fields
            project_holding_type="RIGHT_OF_RESIDENCE_APARTMENT",
            project_building_type="BLOCK_OF_FLATS",
            project_postal_code="00100",
            project_city="Helsinki",
            room_count=3,
            debt_free_sales_price=200000,
            right_of_occupancy_payment=50000,
        )

        # send etuovi xml file to update last_mapped_to_etuovi field for this apartment
        call_command("send_etuovi_xml_file")
        apartment_last_mapped_to_etuovi = MappedApartment.objects.get(
            apartment_uuid=apartment.uuid
        ).last_mapped_to_etuovi
        assert apartment_last_mapped_to_etuovi is not None

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        success_uuids = [item["uuid"] for item in response.data["etuovi"]["success"]]
        assert str(apartment.uuid) in success_uuids
        assert str(apartment.uuid) not in [
            item["uuid"] for item in response.data["etuovi"]["fail"]
        ]
        assert isinstance(
            response.data["etuovi"]["success"][0]["last_mapped"], datetime.datetime
        )
        assert response.data["etuovi"]["success"][0]["last_mapped"] is not None

        apartment.delete(refresh=True)

    @pytest.mark.usefixtures("elastic_apartments")
    def test_integration_status_etuovi_with_missing_fields(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that apartments with missing Etuovi required fields are in fail list"""
        # Create apartment missing some Etuovi required fields
        apartment = ApartmentMinimalFactory.create(
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_etuovi=True,
            _language="fi",
            # Missing: room_count, right_of_occupancy_payment
            project_holding_type="RIGHT_OF_RESIDENCE_APARTMENT",
            project_building_type="BLOCK_OF_FLATS",
            project_postal_code="00100",
            project_city="Helsinki",
            room_count=None,  # Missing
            debt_free_sales_price=200000,
            project_ownership_type="HASO",
            right_of_occupancy_payment=None,  # Missing
        )

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        success_uuids = [item["uuid"] for item in response.data["etuovi"]["success"]]
        assert str(apartment.uuid) not in success_uuids

        fail_items = [
            item
            for item in response.data["etuovi"]["fail"]
            if item["uuid"] == str(apartment.uuid)
        ]
        assert len(fail_items) == 1
        assert "room_count" in fail_items[0]["missing_fields"]
        assert "right_of_occupancy_payment" in fail_items[0]["missing_fields"]

        apartment.delete(refresh=True)

    @pytest.mark.usefixtures("elastic_apartments", "not_sending_oikotie_ftp")
    def test_integration_status_oikotie_with_all_required_fields(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that apartments with all Oikotie required fields are in success list"""
        # Create apartment with all Oikotie required fields
        apartment = ApartmentMinimalFactory.create(
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_oikotie=True,
            _language="fi",
            # All Oikotie required fields
            living_area=50.5,
            financing_fee=200,
            maintenance_fee=300,
            water_fee=50,
            parking_fee=100,
            debt_free_sales_price=200000,
            sales_price=250000,
            url="https://example.com/apartment",
            project_coordinate_lat=60.1699,
            project_coordinate_lon=24.9384,
            project_ownership_type="HITAS",
        )

        # send oikotie xml file to update last_mapped_to_oikotie for this apartment
        call_command("send_oikotie_xml_file")

        apartment_last_mapped_to_oikotie = MappedApartment.objects.get(
            apartment_uuid=apartment.uuid
        ).last_mapped_to_oikotie
        assert apartment_last_mapped_to_oikotie is not None

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        success_uuids = [item["uuid"] for item in response.data["oikotie"]["success"]]
        assert str(apartment.uuid) in success_uuids
        assert str(apartment.uuid) not in [
            item["uuid"] for item in response.data["oikotie"]["fail"]
        ]
        assert isinstance(
            response.data["oikotie"]["success"][0]["last_mapped"], datetime.datetime
        )
        assert response.data["oikotie"]["success"][0]["last_mapped"] is not None

        apartment.delete(refresh=True)

    @pytest.mark.usefixtures("elastic_apartments")
    def test_integration_status_oikotie_with_missing_fields(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that apartments with missing Oikotie required fields are in fail list"""
        # Create apartment missing some Oikotie required fields
        apartment = ApartmentMinimalFactory.create(
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_oikotie=True,
            _language="fi",
            # Missing: living_area, url, parking_fee
            financing_fee=200,
            maintenance_fee=300,
            water_fee=50,
            parking_fee=None,  # Missing
            debt_free_sales_price=200000,
            sales_price=250000,
            url=None,  # Missing
            living_area=None,  # Missing
        )

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        success_uuids = [item["uuid"] for item in response.data["oikotie"]["success"]]
        assert str(apartment.uuid) not in success_uuids

        fail_items = [
            item
            for item in response.data["oikotie"]["fail"]
            if item["uuid"] == str(apartment.uuid)
        ]
        assert len(fail_items) == 1
        assert "living_area" in fail_items[0]["missing_fields"]
        assert "url" in fail_items[0]["missing_fields"]
        assert "parking_fee" in fail_items[0]["missing_fields"]

        apartment.delete(refresh=True)

    @pytest.mark.usefixtures("elastic_apartments")
    def test_integration_status_excludes_sold_apartments(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that sold apartments are excluded from validation"""
        # Create sold apartment with all required fields
        apartment = ApartmentMinimalFactory.create(
            apartment_state_of_sale=ApartmentStateOfSale.SOLD,
            publish_on_etuovi=True,
            publish_on_oikotie=True,
            _language="fi",
            # All required fields present
            project_holding_type="RIGHT_OF_RESIDENCE_APARTMENT",
            project_building_type="BLOCK_OF_FLATS",
            project_postal_code="00100",
            project_city="Helsinki",
            room_count=3,
            debt_free_sales_price=200000,
            right_of_occupancy_payment=50000,
            living_area=50.5,
            financing_fee=200,
            maintenance_fee=300,
            water_fee=50,
            parking_fee=100,
            sales_price=250000,
            url="https://example.com/apartment",
        )

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        # Sold apartment should not appear in either success or fail
        etuovi_success_uuids = [
            item["uuid"] for item in response.data["etuovi"]["success"]
        ]
        oikotie_success_uuids = [
            item["uuid"] for item in response.data["oikotie"]["success"]
        ]
        assert str(apartment.uuid) not in etuovi_success_uuids
        assert str(apartment.uuid) not in [
            item["uuid"] for item in response.data["etuovi"]["fail"]
        ]
        assert str(apartment.uuid) not in oikotie_success_uuids
        assert str(apartment.uuid) not in [
            item["uuid"] for item in response.data["oikotie"]["fail"]
        ]

        apartment.delete(refresh=True)

    @pytest.mark.usefixtures("elastic_apartments")
    def test_integration_status_only_validates_published_apartments(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that only apartments with publish flags are validated"""
        # Create apartment with all required fields but not published
        apartment = ApartmentMinimalFactory.create(
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_etuovi=False,
            publish_on_oikotie=False,
            _language="fi",
            # All required fields present
            project_holding_type="RIGHT_OF_RESIDENCE_APARTMENT",
            project_building_type="BLOCK_OF_FLATS",
            project_postal_code="00100",
            project_city="Helsinki",
            room_count=3,
            debt_free_sales_price=200000,
            right_of_occupancy_payment=50000,
            living_area=50.5,
            financing_fee=200,
            maintenance_fee=300,
            water_fee=50,
            parking_fee=100,
            sales_price=250000,
            url="https://example.com/apartment",
        )

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        # Unpublished apartment should not appear in validation results
        etuovi_success_uuids = [
            item["uuid"] for item in response.data["etuovi"]["success"]
        ]
        oikotie_success_uuids = [
            item["uuid"] for item in response.data["oikotie"]["success"]
        ]
        assert str(apartment.uuid) not in etuovi_success_uuids
        assert str(apartment.uuid) not in [
            item["uuid"] for item in response.data["etuovi"]["fail"]
        ]
        assert str(apartment.uuid) not in oikotie_success_uuids
        assert str(apartment.uuid) not in [
            item["uuid"] for item in response.data["oikotie"]["fail"]
        ]

        apartment.delete(refresh=True)

    @pytest.mark.usefixtures("elastic_apartments")
    def test_integration_status_handles_empty_results(
        self, drupal_server_api_client  # noqa: F811
    ):
        """Test that endpoint handles case when no apartments match criteria"""
        # Make all apartments sold
        make_apartments_sold_in_elastic()

        response = drupal_server_api_client.get(
            reverse("connections:Connections-integration-status")
        )

        assert response.status_code == 200
        assert response.data["etuovi"]["success"] == []
        assert response.data["etuovi"]["fail"] == []
        assert response.data["oikotie"]["success"] == []
        assert response.data["oikotie"]["fail"] == []
