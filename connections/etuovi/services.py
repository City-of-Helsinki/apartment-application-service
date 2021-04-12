import logging
from django_etuovi.etuovi import create_xml_file
from elasticsearch_dsl import Search

from connections.etuovi.etuovi_mapper import map_apartment_to_item

_logger = logging.getLogger(__name__)


def fetch_apartments_for_sale():
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale="FOR_SALE")
    )
    s_obj.execute()
    scan = s_obj.scan()

    items = []

    for hit in scan:
        try:
            items.append(map_apartment_to_item(hit))
        except ValueError as e:
            _logger.warning(f"Could not map apartment {hit.uuid}:", str(e))
            pass
    if not items:
        _logger.warning(
            "There were no apartments to map or could not map any apartments"
        )
    _logger.info(f"Succefully mapped {len(items)} apartments for sale")
    return items


def create_xml(items):
    try:
        xml_filename = create_xml_file(items)
        _logger.info(f"Created XML file for apartments in location {xml_filename}")
        return xml_filename

    except Exception as e:
        _logger.error("Apartment XML not created:", str(e))
        return None
