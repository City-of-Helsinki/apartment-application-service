from decimal import Decimal
import logging

from django.conf import settings
from elasticsearch_dsl import connections

_logger = logging.getLogger(__name__)

from collections.abc import Callable
from typing import List, Union


def create_elastic_connection() -> None:
    """
    Creates the ElasticSearch connection with the url provided in the settings.
    The ElasticSearch connection needs to be established before it can be accessed.
    """
    http_auth = None
    if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
        http_auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

    connections.create_connection(
        hosts=[settings.ELASTICSEARCH_URL],
        port=settings.ELASTICSEARCH_PORT,
        http_auth=http_auth,
        # transfer to using ES via Openshift service, which uses self-signed certs
        verify_certs=False,
    )


def convert_price_from_cents_to_eur(price: int) -> Decimal:
    """
    Prices are saved as cents in ElasticSearch. Convert to EUR.
    """
    return Decimal(price / 100.0)


def map_document(
    document: "ApartmentDocument", document_mapper_func: Callable
) -> Union[dict, None]:
    """Maps an ApartmentDocument into the correct dictionary using the given
    mapper function passed to it. Handles and logs errors.

    Args:
        document (ApartmentDocument): ApartmentDocument
        document_mapper_func (Callable): Function that returns a mapping info dict

    Returns:
        dict: `{"field": value}` dictionary that will be mapped to XML
    """
    mapped: dict = None
    try:
        mapped = document_mapper_func(document)
    except ValueError as e:
        _logger.error(e)
        _logger.warning(
            f"{document_mapper_func.__name__}: Could not map {document.uuid}/{document}:",  # noqa: E501
            exc_info=True
        )
    return mapped
