import logging
import os
from django.conf import settings
from django_etuovi.etuovi import create_xml_file
from elasticsearch_dsl import Search
from typing import Tuple

from connections.enums import ApartmentStateOfSale
from connections.etuovi.etuovi_mapper import map_apartment_to_item

_logger = logging.getLogger(__name__)


def fetch_apartments_for_sale() -> list:
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
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


def create_xml(items: list) -> Tuple[str, str]:
    path = settings.APARTMENT_DATA_TRANSFER_PATH
    if not items:
        _logger.warning("Apartment XML not created: there were no apartments")
        return path, None
    if not os.path.exists(path):
        os.mkdir(path)
    try:
        path, xml_filename = create_xml_file(items, path)
        _logger.info(
            f"Created XML file for apartments in location {path}/{xml_filename}"
        )
        return path, xml_filename

    except Exception as e:
        _logger.error("Apartment XML not created:", str(e))
        return None
