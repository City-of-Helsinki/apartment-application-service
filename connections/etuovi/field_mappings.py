from django_etuovi.enums import (
    Condition,
    HoldingType,
    LinkType,
    RealtyImageType,
    RealtyOption,
    TextKey,
    TradeType,
)

# (elastic_field_name: etuovi_text_key)
TEXT_MAPPING = {
    "additional_information": TextKey.INFO1,
    "apartment_structure": TextKey.FLATSTRUCTURE,
    "balcony_description": TextKey.BALCONYDESC,
    "project_constructor": TextKey.CONSTRUCTOR,
    "floor": TextKey.FLOOR,
    "project_heating_options": TextKey.HEATING,
    "project_site_renter": TextKey.LOTRENTER,
    "project_zoning_info": TextKey.ZONINGINFO,
    "project_housing_manager": TextKey.HOUSEMANAGER,
    "kitchen_appliances": TextKey.KITCHENCABINET,
    "project_construction_materials": TextKey.MATERIAL,
    "project_roof_material": TextKey.ROOF,
    "parking_fee_explanation": TextKey.PARKINGSPACE_INFO,
    "project_description": TextKey.PRESENTATION,
    "services_description": TextKey.SERVICES,
    "storage_description": TextKey.STORAGEDESC,
    "view_description": TextKey.VIEWDESC,
    "water_fee": TextKey.CHARGESWATER,
}


# (elastic_field_name: etuovi_link_type)
EXTRA_LINK_MAPPING = {
    "project_attachment_urls": LinkType.EXTRA_INFO_1,
    "project_virtual_presentation_url": LinkType.VIRTUAL,
}


# (elastic_field_name: etuovi_image_type)
IMAGE_MAPPING = {
    "project_main_image_url": RealtyImageType.MAIN_IMAGE,
    "project_image_urls": RealtyImageType.GENERAL_IMAGE,
    "image_urls": RealtyImageType.GENERAL_IMAGE,
}


# (elastic_field_name: etuovi_realty_option)
REALTY_OPTION_MAPPING = {
    "has_balcony": RealtyOption.BALCONY,
    "project_has_elevator": RealtyOption.ELEVATOR,
    "has_apartment_sauna": RealtyOption.OWN_SAUNA,
    "project_has_sauna": RealtyOption.HOUSING_SAUNA,
    "has_yard": RealtyOption.YARD,
}


# (elastic_field_value: etuovi_condition)
CONDITION_MAPPING = {
    "Uusi": Condition.GOOD,
}


# (elastic_field_value: etuovi_holding_type)
HOLDING_TYPE_MAPPING = {
    "Asumisoikeushuoneisto": HoldingType.RIGHT_OF_OCCUPANCY,
    "Osakehuoneisto": HoldingType.OWN,
}


# (elastic_field_value: etuovi_trade_type)
TRADE_TYPE_MAPPING = {
    "Asumisoikeushuoneisto": TradeType.RIGHT_OF_OCCUPANCY,
    "Osakehuoneisto": TradeType.SALE,
}


# elastic_field_name
PRICE_FIELDS = [
    "financing_fee",
    "debt_free_sales_price",
    "maintenance_fee",
    "sales_price",
    "parking_fee",
    "price_m2",
    "water_fee",
]


# (elastic_field_name: etuovi_field_name)
ITEM_FIELDS = {
    "project_city": "town",
    "project_construction_year": "buildyear",
    "debt_free_sales_price": "debtfreeprice",
    "project_district": "quarteroftown",
    "financing_fee": "chargesfinancebasemonth",
    "floor_max": "floors",
    "uuid": "cust_itemcode",
    "project_energy_class": "energyclass",
    "living_area": "livingaream2",
    "maintenance_fee": "chargesmaintbasemonth",
    "parking_fee": "charges_parkingspace",
    "project_postal_code": "postcode",
    "price_m2": "price_m2",
    "project_realty_id": "realtyidentifier",
    "room_count": "roomcount",
    "sales_price": "price",
    "showing_times": ["showingdate", "showing_date2"],
    "project_site_area": "lotarea",
    "project_site_owner": "lotholding",
    "project_street_address": "street",
    "water_fee_explanation": "chargeswater_period",
    "project_zoning_status": "zoningname",
    "project_parkingplace_count": "rc_parkingspace_count",
}
