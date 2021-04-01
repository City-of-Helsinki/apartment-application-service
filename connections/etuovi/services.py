import logging
from elasticsearch_dsl import Search

from django_etuovi.etuovi import create_xml_file

from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.utils import create_elastic_connection


_logger = logging.getLogger(__name__)
create_elastic_connection()


def fetch_apartments():
    s_obj = (
        Search()
        .exclude("match", _language="en")
        .exclude("match", apartment_state_of_sale="SOLD")
    )
    s_obj.execute()
    scan = s_obj.scan()

    items = []

    for hit in scan:
        try:
            m = map_apartment_to_item(hit)
            items.append(m)
        except ValueError as e:
            _logger.warn(f"Could not map apartment {hit.meta.id}:", str(e))
            pass

    return items


def create_xml(items):
    try:
        xml_filename = create_xml_file(items)
        return xml_filename

    except Exception as e:
        _logger.error("Apartment XML not created:", str(e))
        return False
