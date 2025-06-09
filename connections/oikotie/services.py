import logging
import os
from typing import Optional, Tuple

from django.conf import settings
from connections.utils import map_document
from django_oikotie.oikotie import create_apartments, create_housing_companies
from django_oikotie.utils import validate_against_schema

from apartment.elastic.documents import ApartmentDocument
from connections.enums import ApartmentStateOfSale
from connections.oikotie.oikotie_mapper import (
    map_oikotie_apartment,
    map_oikotie_housing_company,
)

_logger = logging.getLogger(__name__)


def fetch_apartments_for_sale() -> Tuple[list, list]:
    """
    Fetch apartments for sale from elasticsearch and map them for Oikotie
    """
    s_obj = (
        ApartmentDocument.search()
        .filter("term", _language="fi")
        .exclude("term", apartment_state_of_sale__keyword=ApartmentStateOfSale.SOLD)
        .filter("term", publish_on_oikotie=True)
    )
    s_obj.execute()
    scan = s_obj.scan()
    apartments = []
    housing_companies = []

    for hit in scan:
        apartment = map_document(hit, map_oikotie_apartment)
        housing = map_document(hit, map_oikotie_housing_company)
        if apartment:
            apartments.append(apartment)
        if housing:
            housing_companies.append(housing)

    if not apartments:
        _logger.warning(
            "There were no apartments to map or could not map any apartments"
        )
    _logger.info(f"Successfully mapped {len(apartments)} apartments for sale")
    return (apartments, housing_companies)


def create_xml_apartment_file(apartments: list) -> Optional[str]:
    """
    Create XML file from apartment list
    """
    path = settings.APARTMENT_DATA_TRANSFER_PATH
    if not apartments:
        _logger.warning("Apartment XML not created: there were no apartments")
        return None
    if not os.path.exists(path):
        os.mkdir(path)
    try:
        ap_file = create_apartments(apartments, path)
        _logger.info(f"Created XML file for apartments in location {path}/{ap_file}")

        _logger.debug("settings.IS_TEST: %s", settings.IS_TEST)

        valid = validate_against_schema(
            settings.OIKOTIE_APARTMENTS_BATCH_SCHEMA, os.path.join(path, ap_file)
        )

        if not valid:
            raise Exception(f"File validation failed: {ap_file}")

        return ap_file
    except Exception as e:
        _logger.error("Apartment XML not created:", {str(e)})
        return None


def create_xml_housing_company_file(housing_companies: list) -> Optional[str]:
    """
    Create XML file from housing company list
    """
    path = settings.APARTMENT_DATA_TRANSFER_PATH
    if not housing_companies:
        _logger.warning(
            "Housing company XML not created: there were no housing companies"
        )
        return None
    if not os.path.exists(path):
        os.mkdir(path)
    try:
        hc_file = create_housing_companies(housing_companies, path)
        _logger.info(
            f"Created XML file for housing_companies in location {path}/{hc_file}"
        )

        valid = validate_against_schema(
            settings.OIKOTIE_HOUSINGCOMPANIES_BATCH_SCHEMA,
            os.path.join(path, hc_file),
        )

        if not valid:
            raise Exception(f"File validation failed: {hc_file}")

        return hc_file
    except Exception as e:
        _logger.error("Housing company XML not created:", {str(e)})
        return None
