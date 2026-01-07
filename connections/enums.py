from enum import Enum
from typing import Type

from apartment.enums import OwnershipType


class Currency(Enum):
    EUR = "EUR"


class Unit(Enum):
    EUR_KK = "EUR/kk"
    M2 = "m2"


class ApartmentStateOfSale(str, Enum):
    FOR_SALE = "FOR_SALE"
    OPEN_FOR_APPLICATIONS = "OPEN_FOR_APPLICATIONS"
    FREE_FOR_RESERVATIONS = "FREE_FOR_RESERVATIONS"
    RESERVED = "RESERVED"
    RESERVED_HASO = "RESERVED_HASO"
    SOLD = "SOLD"


class ProjectStateOfSale(str, Enum):
    PRE_MARKETING = "PRE_MARKETING"
    FOR_SALE = "FOR_SALE"
    PROCESSING = "PROCESSING"
    READY = "READY"


class EtuoviEnergyClass(Enum):
    """
    Allowed energy classes for Etuovi
    """

    A = "A"
    A2007 = "A2007"
    B = "B"
    B2007 = "B2007"
    C = "C"
    C2007 = "C2007"
    D = "D"
    D2007 = "D2007"
    E = "E"
    E2007 = "E2007"
    F = "F"
    F2007 = "F2007"
    G = "G"
    G2007 = "G2007"
    H = "H"


class OikotieHousingCompanyRequiredFields(Enum):
    project_housing_company = "project_housing_company"
    project_estate_agent_email = "project_estate_agent_email"
    project_street_address = "project_street_address"
    project_postal_code = "project_postal_code"
    project_city = "project_city"
    project_coordinate_lat = "project_coordinate_lat"
    project_coordinate_lon = "project_coordinate_lon"
    project_new_development_status = "project_new_development_status"
    project_building_type = "project_building_type"
    project_holding_type = "project_holding_type"


class OikotieApartmentRequiredFields(Enum):
    living_area = "living_area"
    financing_fee = "financing_fee"
    maintenance_fee = "maintenance_fee"
    water_fee = "water_fee"
    parking_fee = "parking_fee"
    debt_free_sales_price = "debt_free_sales_price"
    sales_price = "sales_price"
    url = "url"


class OikotieApartmentRequiredFieldsHITAS(Enum):
    """Oikotie required fields for HITAS apartments (includes debt_free_sales_price)"""
    living_area = "living_area"
    financing_fee = "financing_fee"
    maintenance_fee = "maintenance_fee"
    water_fee = "water_fee"
    parking_fee = "parking_fee"
    debt_free_sales_price = "debt_free_sales_price"
    sales_price = "sales_price"
    url = "url"


class OikotieApartmentRequiredFieldsNonHITAS(Enum):
    """Oikotie required fields for non-HITAS apartments (excludes debt_free_sales_price)"""
    living_area = "living_area"
    financing_fee = "financing_fee"
    maintenance_fee = "maintenance_fee"
    water_fee = "water_fee"
    parking_fee = "parking_fee"
    sales_price = "sales_price"
    url = "url"


class EtuoviApartmentRequiredFields(Enum):
    project_holding_type = "project_holding_type"
    project_building_type = "project_building_type"
    project_postal_code = "project_postal_code"
    project_city = "project_city"
    room_count = "room_count"
    debt_free_sales_price = "debt_free_sales_price"
    right_of_occupancy_payment = "right_of_occupancy_payment"


class EtuoviApartmentRequiredFieldsHITAS(Enum):
    """Etuovi required fields for HITAS apartments (includes debt_free_sales_price, excludes right_of_occupancy_payment)"""
    project_holding_type = "project_holding_type"
    project_building_type = "project_building_type"
    project_postal_code = "project_postal_code"
    project_city = "project_city"
    room_count = "room_count"
    debt_free_sales_price = "debt_free_sales_price"


class EtuoviApartmentRequiredFieldsHASO(Enum):
    """Etuovi required fields for HASO apartments (includes right_of_occupancy_payment, excludes debt_free_sales_price)"""
    project_holding_type = "project_holding_type"
    project_building_type = "project_building_type"
    project_postal_code = "project_postal_code"
    project_city = "project_city"
    room_count = "room_count"
    right_of_occupancy_payment = "right_of_occupancy_payment"


def get_etuovi_required_fields_for_ownership_type(
    ownership_type: str,
) -> Type[Enum]:
    """
    Returns the appropriate Etuovi required fields enum based on ownership type.

    Args:
        ownership_type: Project ownership type (e.g., "HITAS", "HASO")

    Returns:
        Enum class with required fields for the ownership type
    """
    if not ownership_type:
        return EtuoviApartmentRequiredFields

    ownership_type_lower = ownership_type.lower()
    if ownership_type_lower == OwnershipType.HASO.value:
        return EtuoviApartmentRequiredFieldsHASO
    elif ownership_type_lower == OwnershipType.HITAS.value:
        return EtuoviApartmentRequiredFieldsHITAS
    else:
        # For other ownership types, use base enum (includes both fields)
        return EtuoviApartmentRequiredFields


def get_oikotie_required_fields_for_ownership_type(
    ownership_type: str,
) -> Type[Enum]:
    """
    Returns the appropriate Oikotie required fields enum based on ownership type.

    Args:
        ownership_type: Project ownership type (e.g., "HITAS", "HASO")

    Returns:
        Enum class with required fields for the ownership type
    """
    if not ownership_type:
        return OikotieApartmentRequiredFields

    ownership_type_lower = ownership_type.lower()
    if ownership_type_lower == OwnershipType.HITAS.value:
        return OikotieApartmentRequiredFieldsHITAS
    else:
        # For non-HITAS (HASO, PUOLIHITAS, etc.), exclude debt_free_sales_price
        return OikotieApartmentRequiredFieldsNonHITAS
