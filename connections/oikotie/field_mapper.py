from django_oikotie.enums import (
    ApartmentType,
    EstateType,
    GeneralConditionLevel,
    ModeOfHabitationType,
    NewDevelopmentStatusChoices,
    SiteType,
)

# (elastic_project_building_type: oikotie_apartment_type)
APARTMENT_TYPE_MAPPING = {
    "BLOCK_OF_FLATS": ApartmentType.BLOCK_OF_FLATS,
    "ROW_HOUSE": ApartmentType.ROW_HOUSE,
    "HOUSE": ApartmentType.HOUSE,
}


# (elastic_project_city: city_id)
CITY_IDS = {
    "Helsinki": 91,
}


# (elastic_project_holding_type: oikotie_estate_type)
ESTATE_TYPE_MAPPING = {
    "CONDOMINIUM": EstateType.CONDOMINIUM,
    "RIGHT_OF_RESIDENCE_APARTMENT": EstateType.REAL_ESTATE,
}


# (elastic_condition: oikotie_general_condition_level)
GENERAL_CONDITION_LEVEL_MAPPING = {
    "Uusi": GeneralConditionLevel.NEW,
}


# (elastic_project_holding_type: oikotie_mode_of_habatation_type)
MODE_OF_HABITATION_MAPPING = {
    "CONDOMINIUM": ModeOfHabitationType.OWNED,
    "RIGHT_OF_RESIDENCE_APARTMENT": ModeOfHabitationType.RIGHT_OF_OCCUPANCY,
}


# (elastic_project_site_owner: oikotie_site)
SITE_MAPPING = {
    "Oma": SiteType.OWNED,
    "Vuokra": SiteType.RENT,
}

# (elastic_project_new_development_status: oikotie_new_development_status)
NEW_DEVELOPMENT_STATUS_MAPPING = {
    "UNDER_PLANNING": NewDevelopmentStatusChoices.UNDER_PLANNING,
    "PRE_MARKETING": NewDevelopmentStatusChoices.PRE_MARKETING,
    "UNDER_CONSTRUCTION": NewDevelopmentStatusChoices.UNDER_CONSTRUCTION,
    "READY_TO_MOVE": NewDevelopmentStatusChoices.READY_TO_MOVE,
}
