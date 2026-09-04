import logging
import os
from typing import Iterable, Optional

from django.conf import settings
from django_etuovi.etuovi import create_xml_file

from apartment.elastic.queries import get_apartments
from connections.enums import ApartmentStateOfSale
from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.utils import (
    build_project_floor_max_by_uuid,
    build_staircase_floor_max_by_uuid,
    map_document,
)

_logger = logging.getLogger(__name__)


def get_apartments_for_etuovi() -> Iterable:
    """
    Returns raw ApartmentDocument objects where publish_on_etuovi=True,
    apartment_state_of_sale is not SOLD, the apartment is published, and
    the project is published.

    Returns:
        Iterator[ApartmentDocument]: Iterator of ApartmentDocument objects
    """

    apartments = get_apartments(
        _language="fi",
        publish_on_etuovi=True,
        apartment_published=True,
        project_published=True,
        include_project_fields=True,
    )
    return (
        apartment
        for apartment in apartments
        if apartment.apartment_state_of_sale != ApartmentStateOfSale.SOLD
    )


def fetch_apartments_for_sale(verbose: bool = False) -> list:
    """
    Fetch apartments for sale from elasticsearch and map them for Etuovi
    """
    scan = list(get_apartments_for_etuovi())
    project_floor_max_lookup = build_project_floor_max_by_uuid(scan)
    staircase_floor_max_lookup = build_staircase_floor_max_by_uuid(scan)

    def map_item(apartment):
        return map_apartment_to_item(
            apartment,
            project_floor_max_lookup=project_floor_max_lookup,
            staircase_floor_max_lookup=staircase_floor_max_lookup,
        )

    items = []

    for hit in scan:
        apartment = map_document(hit, map_item)
        if apartment:
            items.append(apartment)

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
