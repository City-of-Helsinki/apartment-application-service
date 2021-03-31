from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from elasticsearch_dsl.utils import AttrList
from typing import List, Optional, Tuple, Union

from django_etuovi.enums import (
    Condition,
    Country,
    HoldingType,
    ItemGroup,
    LinkType,
    RealtyGroup,
    RealtyImageType,
    RealtyOption,
    RealtyType,
    TextKey,
    TextLanguage,
)
from django_etuovi.items import Coordinate, ExtraLink, Image, Item, Scontact, Text
from connections.elastic_models import Apartment
from connections.enums import Currency, Unit
from connections.etuovi.field_mapper import (
    CONDITION_MAPPING,
    HOLDING_TYPE_MAPPING,
    TRADE_TYPE_MAPPING,
)
from connections.utils import convert_price_from_cents_to_eur


def handle_field_value(field: Union[str, AttrList, None]) -> str:
    """
    A generator that returns each instance of a list if the given field
    is of type AttrList. Otherwise returns the literal value.
    """
    if isinstance(field, AttrList):
        for f in field:
            yield f
    else:
        yield field


def map_decimal(elastic_apartment: Apartment, field_name: str) -> Optional[Decimal]:
    """
    Returns a decimal of the given ElasticSearch float field.
    """
    elastic_value = getattr(elastic_apartment, field_name, None)
    if elastic_value:
        return Decimal(elastic_value)
    else:
        return None


def map_price(elastic_apartment: Apartment, field_name: str) -> Optional[Decimal]:
    """
    Returns the Decimal of an ElasticSearch price field. The prices
    are saved as cents in ElasticSearch so convert the value to Euros.
    """
    elastic_value = getattr(elastic_apartment, field_name, None)
    if elastic_value:
        return convert_price_from_cents_to_eur(elastic_value)
    else:
        return None


def get_showing_datetime_with_index(
    elastic_apartment: Apartment, index: int
) -> Optional[datetime]:
    """
    Returns a showing date from the showing_times list with the given index.
    Add some extra logic to make sure that the showing_times field is actually
    a list and it contains a datetime.
    """
    showing_date = getattr(elastic_apartment, "showing_times", None)
    if (
        isinstance(showing_date, AttrList)
        and len(showing_date) > index
        and isinstance(showing_date[index], datetime)
    ):
        return showing_date[index]
    else:
        return None


def map_showing_date(elastic_apartment: Apartment, index: int) -> Optional[datetime]:
    """
    Returns a showing date from the showing_times list with the given index.
    """
    showing_date = get_showing_datetime_with_index(elastic_apartment, index)
    if showing_date:
        return showing_date
    else:
        return None


def map_showing_end_time(elastic_apartment: Apartment, index: int) -> Optional[str]:
    """
    Returns a showing end time from the showing_times list with the given index.
    End time should be specified as "hh:mm" and because ElasticSearch does not
    provide an ending time, we estimate it to be 1 hour from the starting time.
    """
    showing_date = get_showing_datetime_with_index(elastic_apartment, index)
    if showing_date:
        return (showing_date + timedelta(hours=1)).strftime("%H:%M")
    else:
        return None


def map_showing_info(elastic_apartment: Apartment, index: int) -> Optional[str]:
    """
    Returns an info text for the given showing time if it exists.
    """
    showing_date = get_showing_datetime_with_index(elastic_apartment, index)
    if showing_date:
        return "Asuntonäytön lopetusaika on arvio."
    else:
        return None


def map_condition(elastic_apartment: Apartment) -> Optional[Condition]:
    """
    Returns the mapped Etuovi condition based on the input value
    from ElasticSearch.
    """
    building_condition = getattr(elastic_apartment, "condition", None)
    if building_condition in CONDITION_MAPPING.keys():
        return CONDITION_MAPPING[building_condition]
    else:
        return None


def map_holding_type(elastic_apartment: Apartment) -> HoldingType:
    """
    Returns the mapped Etuovi holding type based on the input
    project_holding_type. Raises an error if the holding type cannot be
    mapped, because this is a required value.
    """
    holding_type = getattr(elastic_apartment, "project_holding_type", None)

    # temporal for broken test data
    if holding_type in ["Condominium"]:
        holding_type = "Osakehuoneisto"

    if holding_type in HOLDING_TYPE_MAPPING.keys():
        return HOLDING_TYPE_MAPPING[holding_type]
    else:
        raise ValueError(
            _(f"project_holding_type {holding_type} not found in HOLDING_TYPE_MAPPING")
        )


def map_item_group(elastic_apartment: Apartment) -> ItemGroup:
    """
    Checks if the given apartment has the project_new_housing flag set and
    returns the ItemGroup value based on this.
    """
    new_housing = getattr(elastic_apartment, "project_new_housing", None)
    if new_housing:
        return ItemGroup.NEW_HOUSING
    else:
        return ItemGroup.DWELLING


def map_realty_group(elastic_apartment: Apartment) -> Optional[RealtyGroup]:
    """
    Checks if the given apartment has the project_new_housing flag set and
    returns the RealtyGroup value based on this.
    """
    new_housing = getattr(elastic_apartment, "project_new_housing", None)
    if new_housing:
        return RealtyGroup.NEW_BUILDING
    else:
        return RealtyGroup.RESIDENTIAL_APARTMENT


def map_realty_type(elastic_apartment: Apartment) -> str:
    """
    Tries to match the given project_building_type value with the options
    in ElasticSearch. Raises an error if the holding type cannot be
    mapped, because this is a required value.
    """
    building_type = getattr(elastic_apartment, "project_building_type", None)
    realty_type_options = {realty_type.value: realty_type for realty_type in RealtyType}

    # temporal for broken test data
    if building_type in ["Flat", "Small house"]:
        building_type = "Kerrostalo"

    if building_type in realty_type_options.keys():
        return realty_type_options[building_type]
    else:
        raise ValueError(
            _(f"project_building_type {building_type} not found in realty_type_options")
        )


def map_trade_type(elastic_apartment: Apartment) -> str:
    """
    Returns the mapped Etuovi trade type based on the input
    project_holding_type. Raises an error if the holding type
    cannot be mapped, because this is a required value.
    """
    holding_type = getattr(elastic_apartment, "project_holding_type", None)

    # temporal for broken test data
    if holding_type in ["Condominium"]:
        holding_type = "Osakehuoneisto"

    if holding_type in TRADE_TYPE_MAPPING.keys():
        return TRADE_TYPE_MAPPING[holding_type]
    else:
        raise ValueError(
            _("project_holding_type %s not found in TRADE_TYPE_MAPPING") % holding_type
        )


def map_coordinates(elastic_apartment: Apartment) -> Optional[List[Coordinate]]:
    """
    Returns a list of coordinates for the given apartment. Return type must be
    a list because of the Etuovi model.
    """
    lat = getattr(elastic_apartment, "project_coordinate_lat", None)
    lon = getattr(elastic_apartment, "project_coordinate_lon", None)
    if lat and lon:
        return [
            Coordinate(
                lat=lat,
                lon=lon,
            )
        ]
    return None


def map_scontacts(elastic_apartment: Apartment) -> Optional[List[Scontact]]:
    """
    Returns a list of estate agent information for the given apartment.
    Return type must be a list because of the Etuovi model.
    """
    name = getattr(elastic_apartment, "project_estate_agent", None)
    email = getattr(elastic_apartment, "project_estate_agent_email", None)
    phone = getattr(elastic_apartment, "project_estate_agent_phone", None)
    if name or email or phone:
        return [
            Scontact(
                scontact_name=name,
                scontact_title="",
                scontact_itempage_email=email,
                scontact_mobilephone="",
                scontact_phone=phone,
                scontact_image_url="",
            )
        ]
    return None


def get_text_mapping(text_key: TextKey, text_value: str) -> Text:
    """
    Returns a Text instance with the mapped key and value.
    """
    return Text(
        text_key=text_key,
        text_value=text_value,
        text_language=TextLanguage.FI,
    )


def map_apartment_to_text_properties(
    elastic_apartment: Apartment,
) -> List[Tuple[TextKey, Union[List[str], str, None]]]:
    """
    Returns a mapping list for each TextKey -> value.
    The corresponding values are mostly from ElasticSearch fields
    with a couple of exceptions.
    """
    return [
        (TextKey.BALCONYDESC, getattr(elastic_apartment, "balcony_description", None)),
        (TextKey.CHARGESWATER, getattr(elastic_apartment, "water_fee", None)),
        (TextKey.CONSTRUCTOR, getattr(elastic_apartment, "project_constructor", None)),
        (
            TextKey.FLATSTRUCTURE,
            getattr(elastic_apartment, "apartment_structure", None),
        ),
        (TextKey.FLOOR, getattr(elastic_apartment, "floor", None)),
        (TextKey.HEATING, getattr(elastic_apartment, "project_heating_options", None)),
        (
            TextKey.HOUSEMANAGER,
            getattr(elastic_apartment, "project_housing_manager", None),
        ),
        (TextKey.INFO1, getattr(elastic_apartment, "additional_information", None)),
        (
            TextKey.KITCHENCABINET,
            getattr(elastic_apartment, "kitchen_appliances", None),
        ),
        (TextKey.LOTRENTER, getattr(elastic_apartment, "project_site_renter", None)),
        (
            TextKey.MATERIAL,
            getattr(elastic_apartment, "project_construction_materials", None),
        ),
        (
            TextKey.PARKINGSPACE_INFO,
            getattr(elastic_apartment, "parking_fee_explanation", None),
        ),
        (TextKey.PRESENTATION, getattr(elastic_apartment, "project_description", None)),
        (TextKey.ROOF, getattr(elastic_apartment, "project_roof_material", None)),
        (TextKey.SERVICES, getattr(elastic_apartment, "services_description", None)),
        (TextKey.SHOWING_ENDTIME, map_showing_end_time(elastic_apartment, 0)),
        (TextKey.SHOWING_ENDTIME2, map_showing_end_time(elastic_apartment, 1)),
        (TextKey.SHOWING_INFO, map_showing_info(elastic_apartment, 0)),
        (TextKey.SHOWING_INFO2, map_showing_info(elastic_apartment, 1)),
        (TextKey.STORAGEDESC, getattr(elastic_apartment, "storage_description", None)),
        (TextKey.VIEWDESC, getattr(elastic_apartment, "view_description", None)),
        (TextKey.ZONINGINFO, getattr(elastic_apartment, "project_zoning_info", None)),
    ]


def map_texts(elastic_apartment: Apartment) -> List[Text]:
    """
    Handles the mapping of Text properties. If the input value is a list,
    transfer it to a comma separated string.
    """
    text_property_mapping = map_apartment_to_text_properties(elastic_apartment)

    texts = []
    for text_key, field_value in text_property_mapping:
        current_texts = []
        if field_value:
            for text_value in handle_field_value(field_value):
                current_texts.append(str(text_value))
            complete_text = ", ".join(current_texts)
            texts.append(get_text_mapping(text_key, complete_text))
    return texts


def get_extra_link_mapping(
    link_url: str, link_type: LinkType, link_urltitle: str = None
) -> ExtraLink:
    """
    Returns an ExtraLink instance with the mapped url, type and title.
    """
    return ExtraLink(
        link_url=link_url,
        linktype_name=link_type,
        link_urltitle=link_urltitle,
    )


def map_apartment_to_link_types(
    elastic_apartment: Apartment,
) -> List[Tuple[LinkType, Union[List[str], str, None]]]:
    """
    Returns a mapping list for each LinkType -> value.
    """
    return [
        (
            LinkType.EXTRA_INFO_1,
            getattr(elastic_apartment, "project_attachment_urls", None),
        ),
        (
            LinkType.VIRTUAL,
            getattr(elastic_apartment, "project_virtual_presentation_url", None),
        ),
    ]


def map_extra_links(elastic_apartment: Apartment) -> List[ExtraLink]:
    """
    Handles the mapping of ExtraLink properties. If the input value is a list of urls,
    create an ExtraLink for each of the urls.
    """
    link_type_mapping = map_apartment_to_link_types(elastic_apartment)

    extra_links = []
    for link_type, field_value in link_type_mapping:
        for link_url in handle_field_value(field_value):
            if link_url:
                image = get_extra_link_mapping(link_url, link_type)
                extra_links.append(image)
    return extra_links


def get_image_mapping(
    image_type: RealtyImageType, image_seq: str, image_url: str
) -> Image:
    """
    Returns an Image instance with the mapped type, sequence and url.
    """
    return Image(
        image_desc="",
        image_realtyimagetype=image_type,
        image_seq=image_seq,
        image_transfer_id=image_seq,
        image_transfer_source=image_url,
        image_url=image_url,
    )


def map_apartment_to_image_types(
    elastic_apartment: Apartment,
) -> List[Tuple[RealtyImageType, Union[List[str], str, None]]]:
    """
    Returns a mapping list for each RealtyImageType -> value.
    """
    return [
        (
            RealtyImageType.GENERAL_IMAGE,
            getattr(elastic_apartment, "project_image_urls", None),
        ),
        (RealtyImageType.GENERAL_IMAGE, getattr(elastic_apartment, "image_urls", None)),
        (
            RealtyImageType.MAIN_IMAGE,
            getattr(elastic_apartment, "project_main_image_url", None),
        ),
    ]


def map_images(elastic_apartment: Apartment) -> List[Image]:
    """
    Handles the mapping of Image properties. If the input value is a list of image urls,
    create an Image for each of the urls.
    """
    image_type_mapping = map_apartment_to_image_types(elastic_apartment)

    images = []
    image_seq = 1
    for image_type, field_value in image_type_mapping:
        for image_url in handle_field_value(field_value):
            if image_url:
                image = get_image_mapping(image_type, str(image_seq), image_url)
                images.append(image)
                image_seq += 1
    return images


def map_apartment_to_realty_options(
    elastic_apartment: Apartment,
) -> List[Tuple[RealtyOption, Optional[bool]]]:
    """
    Returns a mapping list for each RealtyOption -> boolean value.
    Each RealtyOption is mapped with a boolean value indicating
    if the given RealtyOption exists in the input apartment.
    """
    return [
        (RealtyOption.BALCONY, getattr(elastic_apartment, "has_balcony", None)),
        (
            RealtyOption.ELEVATOR,
            getattr(elastic_apartment, "project_has_elevator", None),
        ),
        (
            RealtyOption.HOUSING_SAUNA,
            getattr(elastic_apartment, "project_has_sauna", None),
        ),
        (
            RealtyOption.OWN_SAUNA,
            getattr(elastic_apartment, "has_apartment_sauna", None),
        ),
        (RealtyOption.YARD, getattr(elastic_apartment, "has_yard", None)),
    ]


def map_realty_options(elastic_apartment: Apartment) -> List[RealtyOption]:
    """
    Handles the mapping of RealtyOption properties. If the RealtyOption exists
    in the input apartment, add it to the realty option list.
    """
    realty_option_mapping = map_apartment_to_realty_options(elastic_apartment)

    realty_options = []
    for realty_option, field_value in realty_option_mapping:
        if field_value is True:
            realty_options.append(realty_option)
    return realty_options


def map_apartment_to_item(elastic_apartment: Apartment) -> Item:
    """
    Maps the ElasticSearch apartment to the Etuovi Item.
    """
    item_dict = {
        "buildyear": getattr(elastic_apartment, "project_construction_year", None),
        "charges_parkingspace": map_price(elastic_apartment, "parking_fee"),
        "chargesfinancebasemonth": map_price(elastic_apartment, "financing_fee"),
        "chargesmaintbasemonth": map_price(elastic_apartment, "maintenance_fee"),
        "chargeswater_period": getattr(
            elastic_apartment, "water_fee_explanation", None
        ),
        "condition_name": map_condition(elastic_apartment),
        "country": Country.FINLAND,
        "coordinate": map_coordinates(elastic_apartment),
        "currency_code": Currency.EUR.value,  # EUR is only supported currency.
        "cust_itemcode": getattr(elastic_apartment, "uuid", None),
        "debtfreeprice": map_price(elastic_apartment, "debt_free_sales_price"),
        "energyclass": getattr(elastic_apartment, "project_energy_class", None),
        "extralink": map_extra_links(elastic_apartment),
        "floors": getattr(elastic_apartment, "floor_max", None),
        "holdingtype": map_holding_type(elastic_apartment),
        "image": map_images(elastic_apartment),
        "itemgroup": map_item_group(elastic_apartment),
        "livingaream2": map_decimal(elastic_apartment, "living_area"),
        "loclvlid": 1,  # If coordinate exists, this needs to be 1.
        "locsourceid": 4,  # If coordinate exists, this needs to be 4.
        "lotarea": map_decimal(elastic_apartment, "project_site_area"),
        "lotareaunitcode": Unit.M2.value,
        "lotholding": getattr(elastic_apartment, "project_site_owner", None),
        "postcode": getattr(elastic_apartment, "project_postal_code", None),
        "price": map_price(elastic_apartment, "sales_price"),
        "price_m2": map_price(elastic_apartment, "price_m2"),
        "quarteroftown": getattr(elastic_apartment, "project_district", None),
        "realtygroup": map_realty_group(elastic_apartment),
        "realtyidentifier": getattr(elastic_apartment, "project_realty_id", None),
        "realty_itemgroup": map_item_group(elastic_apartment),
        "realtytype": map_realty_type(elastic_apartment),
        "realtyoption": map_realty_options(elastic_apartment),
        "rc_parkingspace_count": getattr(
            elastic_apartment, "project_parkingplace_count", None
        ),
        "roomcount": getattr(elastic_apartment, "room_count", None),
        "scontact": map_scontacts(elastic_apartment),
        "showingdate": map_showing_date(elastic_apartment, 0),
        "showing_date2": map_showing_date(elastic_apartment, 1),
        "street": getattr(elastic_apartment, "project_street_address", None),
        "supplier_source_itemcode": settings.ETUOVI_SUPPLIER_SOURCE_ITEMCODE,
        "text": map_texts(elastic_apartment),
        "town": getattr(elastic_apartment, "project_city", None),
        "tradetype": map_trade_type(elastic_apartment),
        "zoningname": getattr(elastic_apartment, "project_zoning_status", None),
    }

    return Item(**item_dict)
