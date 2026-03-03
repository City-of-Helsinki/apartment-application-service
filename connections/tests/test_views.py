"""
Unit tests for connections service helper functions
"""

from unittest.mock import Mock, patch

import pytest  # noqa: F401
import requests
import time
from django.conf import settings
from conftest import integration_test

from apartment.elastic.queries import (
    get_apartment,
    get_apartments,
    get_project,
    get_projects,
)
from apartment.enums import OwnershipType
from connections.enums import (
    ApartmentStateOfSale,
    EtuoviApartmentRequiredFields,
    get_etuovi_required_fields_for_ownership_type,
    get_oikotie_required_fields_for_ownership_type,
    OikotieApartmentRequiredFields,
)
from connections.etuovi.services import get_apartments_for_etuovi
from connections.oikotie.services import get_apartments_for_oikotie
from connections.utils import validate_apartment_required_fields


@integration_test
def test_fetch_all_adaptive_pagination():
    """
    Verify _fetch_all works with real Drupal API. Exercises adaptive
    pagination (size=1000 with short timeout, fallback to size=100 on timeout).
    Uses real DrupalSearchClient (no mock).
    """
    import apartment.elastic.queries as queries

    queries._client = None

    sources = queries._fetch_all(
        "apartments",
        params={
            "project_ownership_type": "hitas",
            "t": str(int(time.time())),
        },
    )
    assert isinstance(sources, list)
    for item in sources:
        assert isinstance(item, dict)
        assert "uuid" in item or "nid" in item


@integration_test
def test_drupal_search_api_integration():
    """
    Verify real Drupal Search API: fetch projects, single project,
    size=1 apartments, then that apartment by uuid.
    """
    import apartment.elastic.queries as queries

    queries._client = None

    projects = get_projects(t=str(int(time.time())))
    assert isinstance(projects, list)
    if not projects:
        pytest.skip("No projects in Drupal API")

    project = projects[0]
    project_uuid = getattr(project, "project_uuid", None) or project.get("project_uuid")
    assert project_uuid

    single_project = get_project(project_uuid)
    assert single_project is not None
    assert (
        getattr(single_project, "project_uuid", None)
        or single_project.get("project_uuid")
    ) == project_uuid

    apartments = get_apartments(limit=1, t=str(int(time.time())))
    assert isinstance(apartments, list)
    if not apartments:
        pytest.skip("No apartments in Drupal API")

    apartment = apartments[0]
    apartment_uuid = getattr(apartment, "uuid", None) or apartment.get("uuid")
    assert apartment_uuid

    single_apartment = get_apartment(apartment_uuid)
    assert single_apartment is not None
    assert (
        getattr(single_apartment, "uuid", None) or single_apartment.get("uuid")
    ) == apartment_uuid


@integration_test
def test_drupal_rest_api_oauth2_bruteforce_protection():
    """
    Five faulty OAuth2 token attempts to Drupal REST API should trigger
    bruteforce protection (429 Too Many Requests on 6th attempt).
    """
    import apartment.elastic.queries as queries

    queries._client = None

    base_url = settings.DRUPAL_SEARCH_API_BASE_URL.rstrip("/")
    url = f"{base_url}/fi/json/projects"
    invalid_tokens = [
        "invalid-token-1",
        "invalid-token-2",
        "invalid-token-3",
        "invalid-token-4",
        "invalid-token-5",
    ]

    for i, token in enumerate(invalid_tokens):
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
        )
        assert (
            response.status_code == 401
        ), f"Attempt {i + 1}: Expected 401, got {response.status_code}"

    response = requests.get(
        url,
        headers={"Authorization": "Bearer invalid-token-6"},
        timeout=10,
        verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
    )
    assert response.status_code == 429, (
        f"Drupal REST API should block bruteforce after 5 failed attempts. "
        f"Got {response.status_code} instead of 429."
    )


class TestValidateApartmentRequiredFields:
    """Test validate_apartment_required_fields function"""

    def test_validate_all_fields_present(self):
        """Test validation when all required fields are present"""
        apartment = Mock()
        apartment.field1 = "value1"
        apartment.field2 = "value2"
        apartment.field3 = 123

        test_fields = [
            "field1",
            "field2",
            "field3",
        ]

        missing_fields = validate_apartment_required_fields(apartment, test_fields)
        assert missing_fields == []

    def test_validate_some_fields_missing(self):
        """Test validation when some required fields are missing"""
        apartment = Mock(spec=[])
        apartment.field1 = "value1"
        apartment.field2 = None  # Missing
        apartment.field3 = ""  # Missing (empty string is falsy)
        # field4 not set at all

        test_fields = [
            "field1",
            "field2",
            "field3",
            "field4",
        ]

        missing_fields = validate_apartment_required_fields(apartment, test_fields)
        assert len(missing_fields) == 3
        assert "field2" in missing_fields
        assert "field3" in missing_fields
        assert "field4" in missing_fields
        assert "field1" not in missing_fields

    def test_validate_all_fields_missing(self):
        """Test validation when all required fields are missing"""
        apartment = Mock(spec=[])

        test_fields = [
            "field1",
            "field2",
            "field3",
        ]

        missing_fields = validate_apartment_required_fields(apartment, test_fields)
        assert missing_fields == ["field1", "field2", "field3"]

    def test_validate_with_etuovi_enum(self):
        """Test validation with EtuoviApartmentRequiredFields enum"""
        apartment = Mock()
        apartment.project_holding_type = "RIGHT_OF_RESIDENCE_APARTMENT"
        apartment.project_building_type = "BLOCK_OF_FLATS"
        apartment.project_postal_code = "00100"
        apartment.project_city = "Helsinki"
        apartment.room_count = 3
        apartment.debt_free_sales_price = 200000
        apartment.right_of_occupancy_payment = 50000

        missing_fields = validate_apartment_required_fields(
            apartment, EtuoviApartmentRequiredFields._member_names_
        )
        assert missing_fields == []

    def test_validate_with_oikotie_enum(self):
        """Test validation with OikotieApartmentRequiredFields enum"""
        apartment = Mock()
        apartment.living_area = 50.5
        apartment.financing_fee = 200
        apartment.maintenance_fee = 300
        apartment.water_fee = 50
        apartment.parking_fee = 100
        apartment.debt_free_sales_price = 200000
        apartment.sales_price = 250000
        apartment.url = "https://example.com"

        missing_fields = validate_apartment_required_fields(
            apartment, OikotieApartmentRequiredFields._member_names_
        )
        assert missing_fields == []

    def test_validate_falsy_values_are_missing(self):
        """Test that falsy values (0, False, empty string) are considered missing"""
        apartment = Mock()
        apartment.field1 = 0  # Falsy
        apartment.field2 = False  # Falsy
        apartment.field3 = ""  # Falsy
        apartment.field4 = []  # Falsy
        apartment.field5 = "value"  # Truthy

        test_fields = [
            "field1",
            "field2",
            "field3",
            "field4",
            "field5",
        ]

        missing_fields = validate_apartment_required_fields(apartment, test_fields)
        assert len(missing_fields) == 4
        assert "field1" in missing_fields
        assert "field2" in missing_fields
        assert "field3" in missing_fields
        assert "field4" in missing_fields
        assert "field5" not in missing_fields


class TestGetApartmentsForEtuovi:
    """Test get_apartments_for_etuovi function"""

    @patch("connections.etuovi.services.get_apartments")
    def test_filters_correctly(self, mock_get_apartments):
        """Test that function filters apartments correctly"""
        mock_get_apartments.return_value = [Mock(), Mock()]

        result = get_apartments_for_etuovi()

        mock_get_apartments.assert_called_once_with(
            _language="fi",
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_etuovi=True,
            include_project_fields=True,
        )

        # Verify result is iterable
        assert hasattr(result, "__iter__")
        # Verify we can iterate over the result
        list(result)  # Consume the iterator


class TestGetApartmentsForOikotie:
    """Test get_apartments_for_oikotie function"""

    @patch("connections.oikotie.services.get_apartments")
    def test_filters_correctly(self, mock_get_apartments):
        """Test that function filters apartments correctly"""
        mock_get_apartments.return_value = [Mock(), Mock()]

        result = get_apartments_for_oikotie()

        mock_get_apartments.assert_called_once_with(
            _language="fi",
            apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE,
            publish_on_oikotie=True,
            include_project_fields=True,
        )

        # Verify result is iterable
        assert hasattr(result, "__iter__")
        # Verify we can iterate over the result
        list(result)  # Consume the iterator


class TestGetOikotieRequiredFieldsForOwnershipType:
    """Test get_oikotie_required_fields_for_ownership_type function"""

    @pytest.mark.parametrize(
        "ownership_type,expected_price_field",
        [
            [OwnershipType.HASO, "right_of_occupancy_payment"],
            [OwnershipType.HITAS, "debt_free_sales_price"],
        ],
    )
    def test_returns_correct_price_field_for_ownership_type(
        self, ownership_type, expected_price_field
    ):
        """Test that function returns the correct required fields for ownership type"""

        assert expected_price_field in get_oikotie_required_fields_for_ownership_type(
            ownership_type.value
        )
        assert expected_price_field in get_etuovi_required_fields_for_ownership_type(
            ownership_type.value
        )
