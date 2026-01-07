"""
Unit tests for connections service helper functions
"""

from enum import Enum
from unittest.mock import Mock, patch

import pytest  # noqa: F401

from connections.enums import (
    EtuoviApartmentRequiredFields,
    OikotieApartmentRequiredFields,
)
from connections.etuovi.services import get_apartments_for_etuovi
from connections.oikotie.services import get_apartments_for_oikotie
from connections.utils import validate_apartment_required_fields


class TestValidateApartmentRequiredFields:
    """Test validate_apartment_required_fields function"""

    def test_validate_all_fields_present(self):
        """Test validation when all required fields are present"""
        apartment = Mock()
        apartment.field1 = "value1"
        apartment.field2 = "value2"
        apartment.field3 = 123

        class TestEnum(Enum):
            field1 = "field1"
            field2 = "field2"
            field3 = "field3"

        missing_fields = validate_apartment_required_fields(apartment, TestEnum)
        assert missing_fields == []

    def test_validate_some_fields_missing(self):
        """Test validation when some required fields are missing"""
        apartment = Mock()
        apartment.field1 = "value1"
        apartment.field2 = None  # Missing
        apartment.field3 = ""  # Missing (empty string is falsy)
        # field4 not set at all

        class TestEnum(Enum):
            field1 = "field1"
            field2 = "field2"
            field3 = "field3"
            field4 = "field4"

        missing_fields = validate_apartment_required_fields(apartment, TestEnum)
        assert len(missing_fields) == 3
        assert "field2" in missing_fields
        assert "field3" in missing_fields
        assert "field4" in missing_fields
        assert "field1" not in missing_fields

    def test_validate_all_fields_missing(self):
        """Test validation when all required fields are missing"""
        apartment = Mock()

        class TestEnum(Enum):
            field1 = "field1"
            field2 = "field2"
            field3 = "field3"

        missing_fields = validate_apartment_required_fields(apartment, TestEnum)
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
            apartment, EtuoviApartmentRequiredFields
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
            apartment, OikotieApartmentRequiredFields
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

        class TestEnum(Enum):
            field1 = "field1"
            field2 = "field2"
            field3 = "field3"
            field4 = "field4"
            field5 = "field5"

        missing_fields = validate_apartment_required_fields(apartment, TestEnum)
        assert len(missing_fields) == 4
        assert "field1" in missing_fields
        assert "field2" in missing_fields
        assert "field3" in missing_fields
        assert "field4" in missing_fields
        assert "field5" not in missing_fields


class TestGetApartmentsForEtuovi:
    """Test get_apartments_for_etuovi function"""

    @patch("connections.etuovi.services.ApartmentDocument")
    def test_filters_correctly(self, mock_apartment_document):
        """Test that function filters apartments correctly"""
        mock_search_obj = Mock()
        mock_search_obj.filter.return_value = mock_search_obj
        mock_search_obj.exclude.return_value = mock_search_obj
        mock_search_obj.execute.return_value = None
        mock_search_obj.scan.return_value = iter([Mock(), Mock()])
        mock_apartment_document.search.return_value = mock_search_obj

        result = get_apartments_for_etuovi()

        # Verify search chain is called correctly
        mock_apartment_document.search.assert_called_once()
        assert mock_search_obj.filter.call_count == 2  # _language and publish_on_etuovi
        mock_search_obj.exclude.assert_called_once()
        mock_search_obj.execute.assert_called_once()
        mock_search_obj.scan.assert_called_once()

        # Verify result is iterable
        assert hasattr(result, "__iter__")
        # Verify we can iterate over the result
        list(result)  # Consume the iterator


class TestGetApartmentsForOikotie:
    """Test get_apartments_for_oikotie function"""

    @patch("connections.oikotie.services.ApartmentDocument")
    def test_filters_correctly(self, mock_apartment_document):
        """Test that function filters apartments correctly"""
        mock_search_obj = Mock()
        mock_search_obj.filter.return_value = mock_search_obj
        mock_search_obj.exclude.return_value = mock_search_obj
        mock_search_obj.execute.return_value = None
        mock_search_obj.scan.return_value = iter([Mock(), Mock()])
        mock_apartment_document.search.return_value = mock_search_obj

        result = get_apartments_for_oikotie()

        # Verify search chain is called correctly
        mock_apartment_document.search.assert_called_once()
        assert (
            mock_search_obj.filter.call_count == 2
        )  # _language and publish_on_oikotie
        mock_search_obj.exclude.assert_called_once()
        mock_search_obj.execute.assert_called_once()
        mock_search_obj.scan.assert_called_once()

        # Verify result is iterable
        assert hasattr(result, "__iter__")
        # Verify we can iterate over the result
        list(result)  # Consume the iterator
