from django_etuovi.enums import Condition, HoldingType, TradeType

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
