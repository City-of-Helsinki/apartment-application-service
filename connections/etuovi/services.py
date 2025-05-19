import logging
import os
from typing import Optional

from django.conf import settings
from django_etuovi.etuovi import create_xml_file

from apartment.elastic.documents import ApartmentDocument
from connections.enums import ApartmentStateOfSale
from connections.etuovi.etuovi_mapper import map_apartment_to_item

_logger = logging.getLogger(__name__)


def fetch_apartments_for_sale(verbose: bool = False) -> list:
    """
    Fetch apartments for sale from elasticsearch and map them for Etuovi
    """
    s_obj = (
        ApartmentDocument.search()
        .filter("term", _language="fi")
        .exclude("term", apartment_state_of_sale__keyword=ApartmentStateOfSale.SOLD)
        .filter("term", publish_on_etuovi=True)
    )
    s_obj.execute()
    scan = s_obj.scan()

    items = []

    for hit in scan:
        try:
            items.append(map_apartment_to_item(hit))
        except ValueError as e:
            print(e)
            _logger.warning(f"Could not map apartment {hit.uuid}/{hit}:", exc_info=True)
    if not items:
        _logger.warning(
            "There were no apartments to map or could not map any apartments"
        )
    _logger.info(f"Successfully mapped {len(items)} apartments for sale")
    return items


def create_xml(items: list) -> Optional[str]:
    """
    Create XML file from apartment list
    """
    path = settings.APARTMENT_DATA_TRANSFER_PATH
    if not items:
        _logger.warning("Apartment XML not created: there were no apartments")
        return None
    if not os.path.exists(path):
        os.mkdir(path)
    try:
        xml_filename = create_xml_file(items, path)
        _logger.info(
            f"Created XML file for apartments in location {path}/{xml_filename}"
        )
        return xml_filename

    except Exception as e:
        _logger.error("Apartment XML not created:", str(e))
        return None
