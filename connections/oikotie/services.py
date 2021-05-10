import logging
from django_oikotie.oikotie import create_apartments, create_housing_companies
from elasticsearch_dsl import Search

from connections.oikotie.oikotie_mapper import (
    map_oikotie_apartment,
    map_oikotie_housing_company,
)

_logger = logging.getLogger(__name__)


def fetch_apartments_for_sale() -> (list, list):
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale="FOR_SALE")
    )
    s_obj.execute()
    scan = s_obj.scan()
    apartments = []
    housing_companies = []

    for hit in scan:
        try:
            apartments.append(map_oikotie_apartment(hit))
        except Exception as e:
            _logger.warning(f"Could not map apartment {hit.uuid}:", str(e))
            pass
        try:
            housing_companies.append(map_oikotie_housing_company(hit))
        except Exception as e:
            _logger.warning(f"Could not map housing company {hit.uuid}:", str(e))
            pass
    if not apartments:
        _logger.warning(
            "There were no apartments to map or could not map any apartments"
        )
    _logger.info(f"Succefully mapped {len(apartments)} apartments for sale")
    return (apartments, housing_companies)


def create_xml_apartment_file(apartments: list) -> str:
    if not apartments:
        _logger.warning("Apartment XML not created: there were no apartments")
        return None
    try:
        ap_file = create_apartments(apartments)
        _logger.info(f"Created XML file for apartments in location {ap_file}")
        return ap_file
    except Exception as e:
        _logger.error("Apartment XML not created:", {str(e)})
        return None


def create_xml_housing_company_file(housing_companies: list) -> str:
    if not housing_companies:
        _logger.warning(
            "Housing company XML not created: there were no housing companies"
        )
        return None
    try:
        hc_file = create_housing_companies(housing_companies)
        _logger.info(f"Created XML file for housing_companies in location {hc_file}")
        return hc_file
    except Exception as e:
        _logger.error("Housing company XML not created:", {str(e)})
        return None
