from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django_etuovi.enums import (
    Condition,
    Country,
    HoldingType,
    ItemGroup,
    LinkType,
    RealtyGroup,
    RealtyImageType,
    RealtyType,
    TextKey,
    TextLanguage,
)
from django_etuovi.items import Coordinate, ExtraLink, Image, Item, Scontact, Text
from elasticsearch_dsl.utils import AttrList
from typing import Union

from connections.elastic_models import Apartment
from connections.etuovi.field_mappings import (
    CONDITION_MAPPING,
    EXTRA_LINK_MAPPING,
    HOLDING_TYPE_MAPPING,
    IMAGE_MAPPING,
    ITEM_FIELDS,
    PRICE_FIELDS,
    REALTY_OPTION_MAPPING,
    TEXT_MAPPING,
    TRADE_TYPE_MAPPING,
)


def handle_field(field: Union[str, AttrList]) -> str:
    if isinstance(field, AttrList):
        for f in field:
            yield f
    else:
        yield field


def map_coordinates(elastic_apartment: Apartment) -> list:
    return [
        Coordinate(
            lat=elastic_apartment["project_coordinate_lat"],
            lon=elastic_apartment["project_coordinate_lon"],
        )
    ]


def get_text_mapping(text_key: TextKey, text_value: str) -> Text:
    return Text(
        text_key=text_key,
        text_value=text_value,
        text_language=TextLanguage.FI,
    )


def map_texts(elastic_apartment: Apartment) -> list:
    texts = []
    for field_name, text_key in TEXT_MAPPING.items():
        current_texts = []
        for text_value in handle_field(elastic_apartment[field_name]):
            current_texts.append(str(text_value))
        texts.append(get_text_mapping(text_key, ", ".join(current_texts)))
    return texts


def get_extra_link_mapping(
    link_url: str, link_type: LinkType, link_urltitle: str = None
) -> ExtraLink:
    return ExtraLink(
        link_url=link_url,
        linktype_name=link_type,
        link_urltitle=link_urltitle,
    )


def map_extra_links(elastic_apartment: Apartment) -> list:
    extra_links = []
    for field_name, link_type in EXTRA_LINK_MAPPING.items():
        for link_url in handle_field(elastic_apartment[field_name]):
            image = get_extra_link_mapping(link_url, link_type)
            extra_links.append(image)
    return extra_links


def get_image_mapping(
    image_type: RealtyImageType, image_seq: str, image_url: str
) -> Image:
    return Image(
        image_desc="",
        image_realtyimagetype=image_type,
        image_seq=image_seq,
        image_transfer_id=image_seq,
        image_transfer_source=image_url,
        image_url=image_url,
    )


def map_images(elastic_apartment: Apartment) -> list:
    images = []
    image_seq = 1
    for field_name, image_type in IMAGE_MAPPING.items():
        for image_url in handle_field(elastic_apartment[field_name]):
            image = get_image_mapping(image_type, str(image_seq), image_url)
            images.append(image)
            image_seq += 1
    return images


def map_scontacts(elastic_apartment: Apartment) -> list:
    return [
        Scontact(
            scontact_name=elastic_apartment["project_estate_agent"],
            scontact_title="",
            scontact_itempage_email=elastic_apartment["project_estate_agent_email"],
            scontact_mobilephone="",
            scontact_phone=elastic_apartment["project_estate_agent_phone"],
            scontact_image_url="",
        )
    ]


def get_elastic_value(
    elastic_apartment: Apartment,
    elastic_field: str,
    elastic_value: Union[str, int, float, AttrList, datetime] = None,
) -> Union[str, int, list, Decimal]:

    if elastic_value is None:
        elastic_value = getattr(elastic_apartment, elastic_field)

    if isinstance(elastic_value, float):
        return Decimal(elastic_value)
    elif isinstance(elastic_value, AttrList):
        return [
            get_elastic_value(elastic_apartment, elastic_field, val)
            for val in elastic_value
        ]
    elif isinstance(elastic_value, int) and elastic_field in PRICE_FIELDS:
        # Prices are saved as cents in ElasticSearch. Convert to EUR.
        return Decimal(elastic_value) / 100
    else:
        return elastic_value


def map_item_fields(elastic_apartment: Apartment) -> dict:
    item_dict = {}
    for elastic_field, etuovi_field in ITEM_FIELDS.items():
        elastic_value = get_elastic_value(elastic_apartment, elastic_field)
        if not elastic_value:
            continue
        elif isinstance(etuovi_field, list):
            item_dict.update(dict(zip(etuovi_field, elastic_value)))
        else:
            item_dict[etuovi_field] = elastic_value
    return item_dict


def map_realty_options(elastic_apartment: Apartment) -> list:
    realty_options = []
    for field_name, realty_option in REALTY_OPTION_MAPPING.items():
        has_realty_option = get_elastic_value(elastic_apartment, field_name)
        if has_realty_option:
            realty_options.append(realty_option)
    return realty_options


def map_condition(elastic_apartment: Apartment) -> Condition:
    building_condition = get_elastic_value(elastic_apartment, "condition")
    return CONDITION_MAPPING[building_condition]


def map_holding_type(elastic_apartment: Apartment) -> HoldingType:
    holding_type = get_elastic_value(elastic_apartment, "project_holding_type")
    return HOLDING_TYPE_MAPPING[holding_type]


def map_item_group(elastic_apartment: Apartment) -> ItemGroup:
    new_housing = get_elastic_value(elastic_apartment, "project_new_housing")
    if new_housing:
        return ItemGroup.NEW_HOUSING
    else:
        return ItemGroup.DWELLING


def map_realty_group(elastic_apartment: Apartment) -> RealtyGroup:
    new_housing = get_elastic_value(elastic_apartment, "project_new_housing")
    if new_housing:
        return RealtyGroup.NEW_BUILDING
    else:
        return RealtyGroup.RESIDENTIAL_APARTMENT


def map_realty_type(elastic_apartment: Apartment) -> str:
    building_type = get_elastic_value(elastic_apartment, "project_building_type")
    realty_type_options = {realty_type.value: realty_type for realty_type in RealtyType}

    realty_type = realty_type_options.get(building_type, None)
    if realty_type:
        return realty_type
    else:
        raise ValueError(
            "building_type %s not found in RealtyType options" % building_type
        )


def map_trade_type(elastic_apartment: Apartment) -> str:
    holding_type = get_elastic_value(elastic_apartment, "project_holding_type")
    return TRADE_TYPE_MAPPING[holding_type]


def map_apartment_to_item(elastic_apartment: Apartment) -> Item:
    item_dict = map_item_fields(elastic_apartment)

    item_dict.update(
        {
            "condition_name": map_condition(elastic_apartment),
            "country": Country.FINLAND,
            "coordinate": map_coordinates(elastic_apartment),
            "currency_code": "EUR",  # EUR is only supported currency.
            "extralink": map_extra_links(elastic_apartment),
            "holdingtype": map_holding_type(elastic_apartment),
            "image": map_images(elastic_apartment),
            "itemgroup": map_item_group(elastic_apartment),
            "loclvlid": 1,  # If coordinate exists, this needs to be 1.
            "locsourceid": 4,  # If coordinate exists, this needs to be 4.
            "lotareaunitcode": "m2",
            "realtygroup": map_realty_group(elastic_apartment),
            "realty_itemgroup": map_item_group(elastic_apartment),
            "realtytype": map_realty_type(elastic_apartment),
            "realtyoption": map_realty_options(elastic_apartment),
            "scontact": map_scontacts(elastic_apartment),
            "supplier_source_itemcode": settings.ETUOVI_SUPPLIER_SOURCE_ITEMCODE,
            "text": map_texts(elastic_apartment),
            "tradetype": map_trade_type(elastic_apartment),
        }
    )
    return Item(**item_dict)
