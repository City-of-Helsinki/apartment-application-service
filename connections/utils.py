import logging
import re
from collections.abc import Callable, Iterable
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Union

from django.utils.html import strip_tags
from lxml import etree

_logger = logging.getLogger(__name__)


def create_elastic_connection() -> None:
    """
    Deprecated: no-op for legacy ElasticSearch connection setup.
    """
    _logger.info("ElasticSearch connection setup is disabled for REST search API.")


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
        new_elem.text = f"\n{text}\n{href}\n"

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


def validate_apartment_required_fields(
    apartment: "ApartmentDocument", required_fields: List[str]  # noqa: F821
) -> List[str]:
    """
    Validates that an apartment has all required fields.

    Args:
        apartment: ApartmentDocument instance
        required_fields: List of required field machine names

    Returns:
        List of missing field machine names (empty if all fields are present)
    """
    missing_fields: List[str] = []
    for field_name in required_fields:
        # Return the enum member name (machine name) in the missing fields list
        if not getattr(apartment, field_name, None):
            missing_fields.append(field_name)
    return missing_fields


def _coerce_floor_value(value) -> Optional[int]:
    """Coerce floor or floor_max to int; return None if invalid or empty."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        stripped = str(value).strip()
        return int(float(stripped)) if stripped else None
    except (ValueError, TypeError):
        return None


def build_project_floor_max_by_uuid(
    apartments: Iterable["ApartmentDocument"],  # noqa: F821
) -> Dict[str, int]:
    """
    Build a lookup of the highest floor-related value per project.

    For each project, considers both floor_max and floor from every apartment
    so export mappers can correct erroneous per-apartment floor_max values.
    """
    project_floor_max: Dict[str, int] = {}
    for apartment in apartments:
        project_uuid = getattr(apartment, "project_uuid", None)
        if not project_uuid:
            continue

        candidates: List[int] = []
        floor_max = _coerce_floor_value(getattr(apartment, "floor_max", None))
        floor = _coerce_floor_value(getattr(apartment, "floor", None))
        if floor_max is not None:
            candidates.append(floor_max)
        if floor is not None:
            candidates.append(floor)
        if not candidates:
            continue

        project_key = str(project_uuid)
        apartment_max = max(candidates)
        current_max = project_floor_max.get(project_key)
        if current_max is None or apartment_max > current_max:
            project_floor_max[project_key] = apartment_max

    return project_floor_max


def resolve_floor_max(
    apartment: "ApartmentDocument",  # noqa: F821
    project_floor_max: Optional[int] = None,
) -> Optional[int]:
    """
    Return floor_max corrected against apartment floor and project maximum.

    Guards against floor_max being lower than the apartment floor or the
    highest floor-related value seen elsewhere in the same project.
    """
    candidates: List[int] = []
    floor_max = _coerce_floor_value(getattr(apartment, "floor_max", None))
    floor = _coerce_floor_value(getattr(apartment, "floor", None))
    if floor_max is not None:
        candidates.append(floor_max)
    if floor is not None:
        candidates.append(floor)
    if project_floor_max is not None:
        candidates.append(int(project_floor_max))

    if not candidates:
        return None
    return max(candidates)
