import logging
from collections.abc import Callable
import re
from decimal import Decimal
from typing import Union

from django.conf import settings
from elasticsearch_dsl import connections
from lxml import etree

_logger = logging.getLogger(__name__)


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
    document: "ApartmentDocument", document_mapper_func: Callable  # noqa: F821
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
            exc_info=True,
        )
    return mapped

def a_tags_to_text(original_text: str) -> str:
    """
    Convert <a> tags to a text and link since the integrations only support a
    limited subset of HTML
    e.g. `<a href="http://foo.bar">Link to page</a>`
    -> `Link to page\n http://foo.bar`
    """

    html_parser = etree.HTMLParser()
    parsed = etree.fromstring(original_text, html_parser)
    a_tags = parsed.findall(".//a")

    # eTree doesn't return the string representations of tags correctly
    # parse tags with regex and use those strings as string replacement patterns
    a_tag_strings = re.findall(r"<a.*?>.*?</a>", original_text, re.MULTILINE)

    for a_tag, a_tag_str in zip(a_tags, a_tag_strings):

        # a_tag_str = etree.tostring(a_tag).decode()
        href = a_tag.attrib["href"]
        text = a_tag.text
        if not a_tag_str or not text:
            continue

        if "mailto:" in href:
            continue

        original_text = original_text.replace(
            a_tag_str,
            f"{text}\n{href}",
        )
        pass

    return original_text
