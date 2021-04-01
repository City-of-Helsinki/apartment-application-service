from django_etuovi.enums import Condition, HoldingType, TradeType, RealtyType

# (elastic_field_value: etuovi_condition)
CONDITION_MAPPING = {
    "Uusi": Condition.GOOD,
}


# (elastic_field_value: etuovi_holding_type)
HOLDING_TYPE_MAPPING = {
    "RIGHT_OF_RESIDENCE_APARTMENT": HoldingType.RIGHT_OF_OCCUPANCY,
    "CONDOMINIUM": HoldingType.OWN,
}


# (elastic_field_value: etuovi_trade_type)
TRADE_TYPE_MAPPING = {
    "RIGHT_OF_RESIDENCE_APARTMENT": TradeType.RIGHT_OF_OCCUPANCY,
    "CONDOMINIUM": TradeType.SALE,
}


# (elastic_project_building_type: oikotie_apartment_type)
REALTY_TYPE_MAPPING = {
    "BLOCK_OF_FLATS": RealtyType.BLOCK_OF_FLATS,
    "ROW_HOUSE": RealtyType.ROW_HOUSE,
    "HOUSE": RealtyType.HOUSE,
}
