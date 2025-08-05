import logging
from collections.abc import Callable
import re
from typing import Union
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils.html import strip_tags
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
    return Decimal(price / 100.0).quantize(Decimal("0.10"), ROUND_HALF_UP)


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
    Convert <a> tags to a <p> tag with text and link since the integrations only support
    a limited subset of HTML
    e.g. `<a href="http://foo.bar">Link to page</a>`
    -> `<p>Link to page\nhttp://foo.bar</p>`
    """

    html_parser = etree.HTMLParser()
    parsed = etree.fromstring(original_text, html_parser)
    a_tags = parsed.findall(".//a")

    # parse through <a> tags in reverse order
    # replace with <p> tags with the href and the text of the link tag
    for a_tag in reversed(a_tags):
        href = a_tag.attrib["href"]
        text = a_tag.text

        if not text:
            continue

        if "mailto:" in href:
            continue

        new_elem = etree.Element("p")
        new_elem.text = f"{text}\n{href}"

        a_tag.getparent().replace(a_tag, new_elem)

    original_text = "".join(
        [etree.tostring(child).decode() for child in parsed.findall("body/")]
    )

    return original_text

def clean_html_tags_from_text(text: str) -> str:
    """
    Strip html tags from a string. Keep the text contents of <p> tags and the href
    attributes of <a> tags.
    """

    # ensure paragraph and line breaks still work even after stripping the HTML
    text = re.sub(r"<br.*?>", r"\n", text)
    text = re.sub(r"<p>(.*?)</p>", r"\1\n\n", text)

    # convert <a> tags to text and link
    # e.g. `<a href="http://foo.bar">Link to page</a>`
    # -> `Link to page\n http://foo.bar`
    text = a_tags_to_text(text)
    text = strip_tags(text)

    return text
