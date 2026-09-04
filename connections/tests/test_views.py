"""
Unit tests for connections service helper functions
"""

import time
from unittest.mock import Mock, patch

import pytest  # noqa: F401
import requests
from django.conf import settings

from apartment.elastic.queries import (
    get_apartment,
    get_apartments,
    get_project,
    get_projects,
)
from apartment.enums import OwnershipType
from conftest import integration_test
from connections.enums import (
    ApartmentStateOfSale,
    EtuoviApartmentRequiredFields,
    get_etuovi_required_fields_for_ownership_type,
    get_oikotie_required_fields_for_ownership_type,
    OikotieApartmentRequiredFields,
)
from connections.etuovi.services import get_apartments_for_etuovi
from connections.oikotie.services import get_apartments_for_oikotie
from connections.tests.factories import ApartmentMinimalFactory
from connections.utils import validate_apartment_required_fields


def _for_sale_vendor_apartment(**overrides):
    """
    Create an apartment that otherwise qualifies for Etuovi and Oikotie export.

    Parameters:
    overrides: Field values that replace the for-sale published defaults.

    Returns:
    Apartment document stored in the test apartment store.
    """
    defaults = {
        "_language": "fi",
        "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE,
        "publish_on_etuovi": True,
        "publish_on_oikotie": True,
        "apartment_published": True,
        "project_published": True,
    }
    defaults.update(overrides)
    return ApartmentMinimalFactory.create(**defaults)


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


@pytest.mark.parametrize("endpoint", ["projects", "apartments"])
@integration_test
def test_drupal_rest_api_oauth2_bruteforce_protection(endpoint):
    """
    Faulty OAuth2 token attempts to Drupal REST API should trigger
    bruteforce protection (429 Too Many Requests after repeated failures).
    """
    import apartment.elastic.queries as queries

    queries._client = None

    base_url = settings.DRUPAL_SEARCH_API_BASE_URL.rstrip("/")
    # Mirror DrupalSearchClient: base URL may already include any language/json prefix.
    url = f"{base_url}/{endpoint}"
    attempt_count = 12

    statuses = []
    for i in range(attempt_count):
        token = f"invalid-token-{endpoint}-{i}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
        )
        statuses.append(response.status_code)
        # Implementation may start returning 429 before or after several 401s.
        assert response.status_code in (401, 429)

    # Across all attempts for this endpoint we must see at least one 429.
    assert any(status == 429 for status in statuses), (
        "Drupal REST API should eventually block bruteforce attempts with 429. "
        f"Statuses seen for {endpoint}: {statuses}"
    )


@integration_test
def test_drupal_oauth_token_bruteforce_protection():
    """
    Ten faulty OAuth2 token exchange attempts (invalid credentials) to
    oauth/token should trigger bruteforce protection (429 on 11th attempt).
    """
    url = settings.DRUPAL_SEARCH_API_TOKEN_URL
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": "invalid-client",
        "client_secret": "invalid-secret",
        "scope": "rest_client",
    }

    for i in range(10):
        response = requests.post(
            url,
            data=data,
            headers=headers,
            timeout=10,
            verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
        )
        assert (
            response.status_code >= 400
        ), f"Attempt {i + 1}: Expected 4xx, got {response.status_code}"

    response = requests.post(
        url,
        data=data,
        headers=headers,
        timeout=10,
        verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
    )
    assert response.status_code == 429, (
        f"Drupal oauth/token should block bruteforce after 10 failed attempts. "
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


_VENDOR_FETCH_EXPECTED_KWARGS = {
    "etuovi": {
        "_language": "fi",
        "publish_on_etuovi": True,
        "apartment_published": True,
        "project_published": True,
        "include_project_fields": True,
    },
    "oikotie": {
        "_language": "fi",
        "publish_on_oikotie": True,
        "apartment_published": True,
        "project_published": True,
        "include_project_fields": True,
    },
}


@pytest.mark.parametrize(
    "fetch_apartments,patch_target,expected_kwargs",
    [
        (
            get_apartments_for_etuovi,
            "connections.etuovi.services.get_apartments",
            _VENDOR_FETCH_EXPECTED_KWARGS["etuovi"],
        ),
        (
            get_apartments_for_oikotie,
            "connections.oikotie.services.get_apartments",
            _VENDOR_FETCH_EXPECTED_KWARGS["oikotie"],
        ),
    ],
    ids=["etuovi", "oikotie"],
)
class TestGetApartmentsForVendor:
    """Vendor fetch helpers query published apartments and exclude SOLD."""

    def test_does_not_filter_by_for_sale_state(
        self, fetch_apartments, patch_target, expected_kwargs
    ):
        """
        - get_apartments is called without apartment_state_of_sale=FOR_SALE.
        - Publish and language filters are still applied.
        """
        with patch(patch_target) as mock_get_apartments:
            mock_get_apartments.return_value = []

            result = fetch_apartments()

            mock_get_apartments.assert_called_once_with(**expected_kwargs)
            assert "apartment_state_of_sale" not in mock_get_apartments.call_args.kwargs
            assert hasattr(result, "__iter__")
            list(result)

    def test_excludes_sold_apartments_from_get_apartments_results(
        self, fetch_apartments, patch_target, expected_kwargs  # noqa: ARG002
    ):
        """
        - Apartments with apartment_state_of_sale=SOLD are not returned.
        - Apartments in any other sale state are returned.
        """
        sold = Mock(apartment_state_of_sale=ApartmentStateOfSale.SOLD)
        reserved = Mock(apartment_state_of_sale=ApartmentStateOfSale.RESERVED)
        for_sale = Mock(apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)

        with patch(patch_target) as mock_get_apartments:
            mock_get_apartments.return_value = [sold, reserved, for_sale]

            result = list(fetch_apartments())

        assert sold not in result
        assert reserved in result
        assert for_sale in result


@pytest.mark.usefixtures("elasticsearch")
@pytest.mark.parametrize(
    "fetch_apartments",
    [get_apartments_for_etuovi, get_apartments_for_oikotie],
    ids=["etuovi", "oikotie"],
)
class TestVendorApartmentFetchExcludesUnpublished:
    """Vendor fetch helpers must skip unpublished apartments and projects."""

    def test_returns_published_apartments_in_published_projects(self, fetch_apartments):
        """
        - Apartments with apartment_published=True and project_published=True
          are returned.
        """
        included = _for_sale_vendor_apartment()

        result_uuids = [apartment.uuid for apartment in fetch_apartments()]

        assert included.uuid in result_uuids

    def test_does_not_return_unpublished_apartments(self, fetch_apartments):
        """
        - Apartments with apartment_published=False are not returned.
        - A published apartment in the same query is still returned.
        """
        included = _for_sale_vendor_apartment(apartment_published=True)
        unpublished = _for_sale_vendor_apartment(apartment_published=False)

        result_uuids = [apartment.uuid for apartment in fetch_apartments()]

        assert included.uuid in result_uuids
        assert unpublished.uuid not in result_uuids

    def test_does_not_return_apartments_in_unpublished_projects(self, fetch_apartments):
        """
        - Apartments with project_published=False are not returned.
        - An apartment in a published project is still returned.
        """
        included = _for_sale_vendor_apartment(project_published=True)
        unpublished_project = _for_sale_vendor_apartment(project_published=False)

        result_uuids = [apartment.uuid for apartment in fetch_apartments()]

        assert included.uuid in result_uuids
        assert unpublished_project.uuid not in result_uuids

    def test_does_not_return_unpublished_apartment_in_unpublished_project(
        self, fetch_apartments
    ):
        """
        - Apartments with apartment_published=False and
          project_published=False are not returned.
        """
        unpublished = _for_sale_vendor_apartment(
            apartment_published=False, project_published=False
        )

        result_uuids = [apartment.uuid for apartment in fetch_apartments()]

        assert unpublished.uuid not in result_uuids


@pytest.mark.usefixtures("elasticsearch")
@pytest.mark.parametrize(
    "fetch_apartments",
    [get_apartments_for_etuovi, get_apartments_for_oikotie],
    ids=["etuovi", "oikotie"],
)
class TestVendorApartmentFetchExcludesSold:
    """Vendor fetch helpers must include unsold apartments and skip SOLD."""

    @pytest.mark.parametrize(
        "state_of_sale",
        [
            ApartmentStateOfSale.FOR_SALE,
            ApartmentStateOfSale.OPEN_FOR_APPLICATIONS,
            ApartmentStateOfSale.FREE_FOR_RESERVATIONS,
            ApartmentStateOfSale.RESERVED,
            ApartmentStateOfSale.RESERVED_HASO,
        ],
    )
    def test_returns_apartments_that_are_not_sold(
        self, fetch_apartments, state_of_sale
    ):
        """
        - Apartments whose sale state is not SOLD are returned.
        """
        included = _for_sale_vendor_apartment(apartment_state_of_sale=state_of_sale)

        result_uuids = [apartment.uuid for apartment in fetch_apartments()]

        assert included.uuid in result_uuids

    def test_does_not_return_sold_apartments(self, fetch_apartments):
        """
        - Apartments with apartment_state_of_sale=SOLD are not returned.
        - An unsold apartment in the same query is still returned.
        """
        included = _for_sale_vendor_apartment(
            apartment_state_of_sale=ApartmentStateOfSale.RESERVED
        )
        sold = _for_sale_vendor_apartment(
            apartment_state_of_sale=ApartmentStateOfSale.SOLD
        )

        result_uuids = [apartment.uuid for apartment in fetch_apartments()]

        assert included.uuid in result_uuids
        assert sold.uuid not in result_uuids


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
