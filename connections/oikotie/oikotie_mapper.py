from datetime import date, datetime, timedelta
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django_oikotie.enums import ApartmentType, NewDevelopmentStatusChoices
from django_oikotie.xml_models.apartment import (
    Apartment,
    Balcony,
    CarParkingCharge,
    City,
    Estate,
    FinancingFee,
    FloorLocation,
    GeneralCondition,
    Lift,
    LivingArea,
    MaintenanceFee,
    ModeOfHabitation,
    NewDevelopmentStatus,
)
from django_oikotie.xml_models.apartment import Picture as ApartmentPicture
from django_oikotie.xml_models.apartment import (
    SalesPrice,
    Sauna,
    ShowingDate1,
    Site,
    SiteArea,
    UnencumberedSalesPrice,
    WaterFee,
    YearOfBuilding,
)
from django_oikotie.xml_models.housing_company import Address
from django_oikotie.xml_models.housing_company import (
    Apartment as HousingCompanyApartment,
)
from django_oikotie.xml_models.housing_company import Coordinates, HousingCompany
from django_oikotie.xml_models.housing_company import Picture as HousingCompanyPicture
from django_oikotie.xml_models.housing_company import RealEstateAgent
from typing import List, Optional

from connections.elastic_models import Apartment as ElasticApartment
from connections.enums import Currency, Unit
from connections.oikotie.field_mapper import (
    APARTMENT_TYPE_MAPPING,
    CITY_IDS,
    ESTATE_TYPE_MAPPING,
    GENERAL_CONDITION_LEVEL_MAPPING,
    MODE_OF_HABITATION_MAPPING,
    NEW_DEVELOPMENT_STATUS_MAPPING,
    SITE_MAPPING,
)
from connections.utils import convert_price_from_cents_to_eur


def map_apartment_type(elastic_apartment: ElasticApartment) -> ApartmentType:
    project_building_type = getattr(elastic_apartment, "project_building_type", None)
    if project_building_type in APARTMENT_TYPE_MAPPING.keys():
        return APARTMENT_TYPE_MAPPING[project_building_type]
    else:
        raise ValueError(
            _("could not map the project_building_type %s") % project_building_type
        )


def map_mode_of_habitation(
    elastic_apartment: ElasticApartment,
) -> ModeOfHabitation:
    project_holding_type = getattr(elastic_apartment, "project_holding_type", None)
    if project_holding_type in MODE_OF_HABITATION_MAPPING.keys():
        return ModeOfHabitation(type=MODE_OF_HABITATION_MAPPING[project_holding_type])
    else:
        raise ValueError(
            _("could not map the project_holding_type %s")
            % elastic_apartment.project_holding_type
        )


def map_city(elastic_apartment: ElasticApartment) -> City:
    project_city = getattr(elastic_apartment, "project_city", None)
    if project_city in CITY_IDS.keys():
        return City(id=CITY_IDS[project_city], value=project_city)
    else:
        raise ValueError(
            _("could not map the project_city %s") % elastic_apartment.project_city
        )


def map_estate(elastic_apartment: ElasticApartment) -> Optional[Estate]:
    project_holding_type = getattr(elastic_apartment, "project_holding_type", None)
    if project_holding_type in ESTATE_TYPE_MAPPING.keys():
        return Estate(type=ESTATE_TYPE_MAPPING[project_holding_type])
    else:
        return None


def map_apartment_pictures(
    elastic_apartment: ElasticApartment,
) -> List[ApartmentPicture]:
    pictures = []

    main_image_url = getattr(elastic_apartment, "project_main_image_url", None)
    if main_image_url:
        pictures.append(
            ApartmentPicture(
                index=1,
                is_floor_plan=False,
                url=main_image_url,
            )
        )

    image_urls = getattr(elastic_apartment, "image_urls", None)
    if image_urls:
        for idx, picture_url in enumerate(image_urls):
            pictures.append(
                ApartmentPicture(index=idx + 2, is_floor_plan=False, url=picture_url)
            )

    return pictures


def map_floor_location(elastic_apartment: ElasticApartment) -> Optional[FloorLocation]:
    if getattr(elastic_apartment, "floor", None) and getattr(
        elastic_apartment, "floor_max", None
    ):
        high = elastic_apartment.floor == elastic_apartment.floor_max
        low = elastic_apartment.floor == 1
        return FloorLocation(
            high=high,
            low=low,
            number=elastic_apartment.floor,
            count=elastic_apartment.floor_max,
            description="",
        )
    else:
        return None


def map_balcony(elastic_apartment: ElasticApartment) -> Optional[Balcony]:
    if getattr(elastic_apartment, "has_balcony", None):
        return Balcony(
            value=elastic_apartment.has_balcony,
            description=elastic_apartment.balcony_description,
        )
    else:
        return None


def map_living_area(elastic_apartment: ElasticApartment) -> Optional[LivingArea]:
    if getattr(elastic_apartment, "living_area", None):
        return LivingArea(unit=Unit.M2.value, area=elastic_apartment.living_area)
    else:
        return None


def map_lift(elastic_apartment: ElasticApartment) -> Optional[Lift]:
    if getattr(elastic_apartment, "project_has_elevator", None):
        return Lift(value=elastic_apartment.project_has_elevator, description="")
    else:
        return None


def map_year_of_building(
    elastic_apartment: ElasticApartment,
) -> Optional[YearOfBuilding]:
    if getattr(elastic_apartment, "project_construction_year", None):
        return YearOfBuilding(
            original=elastic_apartment.project_construction_year, description=""
        )
    else:
        return None


def map_general_condition(
    elastic_apartment: ElasticApartment,
) -> Optional[GeneralCondition]:
    if (
        getattr(elastic_apartment, "condition", None)
        and elastic_apartment.condition in GENERAL_CONDITION_LEVEL_MAPPING.keys()
    ):
        return GeneralCondition(
            level=GENERAL_CONDITION_LEVEL_MAPPING[elastic_apartment.condition],
            description="",
        )
    else:
        return None


def map_site(elastic_apartment: ElasticApartment) -> Optional[Site]:
    if (
        getattr(elastic_apartment, "project_site_owner", None)
        and elastic_apartment.project_site_owner in SITE_MAPPING.keys()
    ):
        return Site(type=SITE_MAPPING[elastic_apartment.project_site_owner])
    else:
        return None


def map_site_area(elastic_apartment: ElasticApartment) -> Optional[SiteArea]:
    if getattr(elastic_apartment, "project_site_area", None):
        return SiteArea(area=elastic_apartment.project_site_area, unit=Unit.M2.value)
    else:
        return None


def map_financing_fee(elastic_apartment: ElasticApartment) -> Optional[FinancingFee]:
    if getattr(elastic_apartment, "financing_fee", None):
        return FinancingFee(
            value=convert_price_from_cents_to_eur(elastic_apartment.financing_fee),
            unit=Unit.EUR_KK.value,
        )
    else:
        return None


def map_maintenance_fee(
    elastic_apartment: ElasticApartment,
) -> Optional[MaintenanceFee]:
    if getattr(elastic_apartment, "maintenance_fee", None):
        return MaintenanceFee(
            value=convert_price_from_cents_to_eur(elastic_apartment.maintenance_fee),
            unit=Unit.EUR_KK.value,
        )
    else:
        return None


def map_water_fee(elastic_apartment: ElasticApartment) -> Optional[WaterFee]:
    if getattr(elastic_apartment, "water_fee", None):
        return WaterFee(
            value=convert_price_from_cents_to_eur(elastic_apartment.water_fee),
            unit=Unit.EUR_KK.value,
        )
    else:
        return None


def map_unencumbered_sales_price(
    elastic_apartment: ElasticApartment,
) -> Optional[UnencumberedSalesPrice]:
    if getattr(elastic_apartment, "debt_free_sales_price", None):
        return UnencumberedSalesPrice(
            value=convert_price_from_cents_to_eur(
                elastic_apartment.debt_free_sales_price
            ),
            currency=Currency.EUR.value,
        )
    else:
        return None


def map_sales_price(elastic_apartment: ElasticApartment) -> Optional[SalesPrice]:
    if getattr(elastic_apartment, "sales_price", None):
        return SalesPrice(
            value=convert_price_from_cents_to_eur(elastic_apartment.sales_price),
            currency=Currency.EUR.value,
        )
    else:
        return None


def map_sauna(elastic_apartment: ElasticApartment) -> Optional[Sauna]:
    if getattr(elastic_apartment, "has_apartment_sauna", None) and getattr(
        elastic_apartment, "project_has_sauna", None
    ):
        return Sauna(
            own=elastic_apartment.has_apartment_sauna,
            common=elastic_apartment.project_has_sauna,
            description="",
        )
    else:
        return None


def map_car_parking_charge(
    elastic_apartment: ElasticApartment,
) -> Optional[CarParkingCharge]:
    if getattr(elastic_apartment, "parking_fee", None):
        return CarParkingCharge(
            value=convert_price_from_cents_to_eur(elastic_apartment.parking_fee),
            unit=Unit.EUR_KK.value,
        )
    else:
        return None


def map_showing_date1(elastic_apartment: ElasticApartment) -> Optional[ShowingDate1]:
    if (
        getattr(elastic_apartment, "showing_times", None)
        and len(elastic_apartment.showing_times) > 0
    ):
        return ShowingDate1(
            value=datetime.strptime(
                elastic_apartment.showing_times[0], "%Y-%m-%dT%H:%M:%S%z"
            ),
            first_showing=True,
        )
    else:
        return None


def map_showing_date2(elastic_apartment: ElasticApartment) -> Optional[date]:
    if (
        getattr(elastic_apartment, "showing_times", None)
        and len(elastic_apartment.showing_times) > 1
    ):
        return datetime.strptime(
            elastic_apartment.showing_times[0], "%Y-%m-%dT%H:%M:%S%z"
        )
    else:
        return None


def map_showing_start_time(
    elastic_apartment: ElasticApartment, index: int
) -> Optional[str]:
    if (
        getattr(elastic_apartment, "showing_times", None)
        and len(elastic_apartment.showing_times) > index
    ):
        return datetime.strptime(
            elastic_apartment.showing_times[index], "%Y-%m-%dT%H:%M:%S%z"
        ).strftime("%H:%M")
    else:
        return None


def map_showing_end_time(
    elastic_apartment: ElasticApartment, index: int
) -> Optional[str]:
    if (
        getattr(elastic_apartment, "showing_times", None)
        and len(elastic_apartment.showing_times) > index
    ):
        estimated_end_time = datetime.strptime(
            elastic_apartment.showing_times[index], "%Y-%m-%dT%H:%M:%S%z"
        ) + timedelta(hours=1)
        return estimated_end_time.strftime("%H:%M")
    else:
        return None


def map_showing_date_explanation(
    elastic_apartment: ElasticApartment, index: int
) -> Optional[str]:
    if (
        getattr(elastic_apartment, "showing_times", None)
        and len(elastic_apartment.showing_times) > index
    ):
        return "Asuntonäytön lopetusaika on arvio."
    else:
        return None


def map_new_development_status(
    elastic_apartment: ElasticApartment,
) -> NewDevelopmentStatusChoices:
    project_new_development_status = getattr(
        elastic_apartment, "project_new_development_status", None
    )
    if project_new_development_status in NEW_DEVELOPMENT_STATUS_MAPPING.keys():
        return NewDevelopmentStatus(
            NEW_DEVELOPMENT_STATUS_MAPPING[project_new_development_status]
        )
    else:
        raise ValueError(
            _("could not map the project_new_development_status %s")
            % project_new_development_status
        )


def form_description(elastic_apartment):
    """
    Fetch link to apartment presentation and add it to the end of project description
    """
    optional_text = "Tarkemman kohde-esittelyn sekä varaustilanteen löydät täältä:"
    main_text = getattr(elastic_apartment, "project_description", None)
    link = getattr(elastic_apartment, "url", None)

    if not main_text and link:
        return "\n".join(filter(None, [optional_text, link]))
    if main_text or link:
        return "\n\n".join(filter(None, [main_text, link]))
    return None


def map_oikotie_apartment(elastic_apartment: ElasticApartment) -> Apartment:
    """
    Maps the ElasticSearch data to the Oikotie Apartment dataclass.
    """
    apartment_field_dict = {
        "type": map_apartment_type(elastic_apartment),
        "new_houses": getattr(elastic_apartment, "project_new_housing", None),
        "key": elastic_apartment.uuid,
        "vendor_identifier": settings.OIKOTIE_VENDOR_ID,
        "mode_of_habitation": map_mode_of_habitation(elastic_apartment),
        "street_address": elastic_apartment.project_street_address,
        "city": map_city(elastic_apartment),
        "estate": map_estate(elastic_apartment),
        "postal_code": getattr(elastic_apartment, "project_postal_code", None),
        "post_office": getattr(elastic_apartment, "project_city", None),
        "region": getattr(elastic_apartment, "project_district", None),
        "latitude": getattr(elastic_apartment, "project_coordinate_lat", None),
        "longitude": getattr(elastic_apartment, "project_coordinate_lon", None),
        "description": form_description(elastic_apartment),
        "supplementary_information": getattr(
            elastic_apartment, "additional_information", None
        ),
        "pictures": map_apartment_pictures(elastic_apartment),
        "virtual_presentation": getattr(
            elastic_apartment, "project_virtual_presentation_url", None
        ),
        "floor_location": map_floor_location(elastic_apartment),
        "number_of_rooms": getattr(elastic_apartment, "room_count", None),
        "room_types": getattr(elastic_apartment, "apartment_structure", None),
        "balcony": map_balcony(elastic_apartment),
        "has_terrace": getattr(elastic_apartment, "has_terrace", None),
        "view": getattr(elastic_apartment, "view_description", None),
        "living_area": map_living_area(elastic_apartment),
        "real_estate_id": getattr(elastic_apartment, "project_realty_id", None),
        "housing_company_name": getattr(
            elastic_apartment, "project_housing_company", None
        ),
        "housing_company_key": getattr(elastic_apartment, "project_uuid", None),
        "disponent": getattr(elastic_apartment, "project_housing_manager", None),
        "real_estate_management": getattr(
            elastic_apartment, "project_sanitation", None
        ),
        "number_of_apartments": getattr(
            elastic_apartment, "project_apartment_count", None
        ),
        "lift": map_lift(elastic_apartment),
        "year_of_building": map_year_of_building(elastic_apartment),
        "heating": ", ".join(elastic_apartment.project_heating_options)
        if getattr(elastic_apartment, "project_heating_options", None)
        else None,
        "general_condition": map_general_condition(elastic_apartment),
        "site": map_site(elastic_apartment),
        "site_area": map_site_area(elastic_apartment),
        "financing_fee": map_financing_fee(elastic_apartment),
        "maintenance_fee": map_maintenance_fee(elastic_apartment),
        "water_fee": map_water_fee(elastic_apartment),
        "water_fee_explanation": getattr(
            elastic_apartment, "water_fee_explanation", None
        ),
        "other_fees": getattr(elastic_apartment, "other_fees", None),
        "car_parking_charge": map_car_parking_charge(elastic_apartment),
        "building_material": ", ".join(elastic_apartment.project_construction_materials)
        if getattr(elastic_apartment, "project_construction_materials", None)
        else None,
        "roof_material": getattr(elastic_apartment, "project_roof_material", None),
        "kitchen_appliances": getattr(elastic_apartment, "kitchen_appliances", None),
        "sauna": map_sauna(elastic_apartment),
        "storage_space": getattr(elastic_apartment, "storage_description", None),
        "services": getattr(elastic_apartment, "services_description", None),
        "unencumbered_sales_price": map_unencumbered_sales_price(elastic_apartment),
        "sales_price": map_sales_price(elastic_apartment),
        "estate_agent_contact_person": getattr(
            elastic_apartment, "project_estate_agent", None
        ),
        "estate_agent_email": getattr(
            elastic_apartment, "project_estate_agent_email", None
        ),
        "estate_agent_telephone": getattr(
            elastic_apartment, "project_estate_agent_phone", None
        ),
        "showing_date1": map_showing_date1(elastic_apartment),
        "showing_start_time1": map_showing_start_time(elastic_apartment, 0),
        "showing_end_time1": map_showing_end_time(elastic_apartment, 0),
        "showing_date_explanation1": map_showing_date_explanation(elastic_apartment, 0),
        "showing_date2": map_showing_date2(elastic_apartment),
        "showing_start_time2": map_showing_start_time(elastic_apartment, 1),
        "showing_end_time2": map_showing_end_time(elastic_apartment, 1),
        "showing_date_explanation2": map_showing_date_explanation(elastic_apartment, 1),
        # for now not using this option:
        # getattr(elastic_apartment, "application_url", None)
        "application_url": None,
        "rc_energyclass": getattr(elastic_apartment, "project_energy_class", None),
        "new_development_status": map_new_development_status(elastic_apartment),
        "time_of_completion": getattr(
            elastic_apartment, "project_completion_date", None
        ),
    }
    return Apartment(**apartment_field_dict)


def map_real_estate_agent(elastic_apartment: ElasticApartment) -> RealEstateAgent:
    vendor_id = settings.OIKOTIE_VENDOR_ID
    contact_email = getattr(elastic_apartment, "project_estate_agent_email", None)
    if vendor_id and contact_email:
        return RealEstateAgent(
            vendor_id=vendor_id,
            contact_email=contact_email,
        )
    else:
        raise ValueError(
            _("could not map the project_estate_agent_email %s") % contact_email
        )


def map_apartment(elastic_apartment: ElasticApartment) -> HousingCompanyApartment:
    return HousingCompanyApartment(types=[map_apartment_type(elastic_apartment)])


def map_address(elastic_apartment: ElasticApartment) -> Address:
    street = getattr(elastic_apartment, "project_street_address", None)
    postal_code = getattr(elastic_apartment, "project_postal_code", None)
    city = getattr(elastic_apartment, "project_city", None)
    region = getattr(elastic_apartment, "project_district", None)
    if street and postal_code and city:
        return Address(
            street=street,
            postal_code=postal_code,
            city=city,
            region=region,
        )
    else:
        address_dict = {
            "project_street_address": street,
            "project_postal_code": postal_code,
            "project_city": city,
        }
        none_values_dict = {k: v for k, v in address_dict.items() if v is None}
        raise ValueError(_("could not map %s") % none_values_dict)


def map_coordinates(elastic_apartment: ElasticApartment) -> Optional[Coordinates]:
    latitude = getattr(elastic_apartment, "project_coordinate_lat", None)
    longitude = getattr(elastic_apartment, "project_coordinate_lon", None)
    if latitude and longitude:
        return Coordinates(
            latitude=latitude,
            longitude=longitude,
        )
    else:
        return None


def map_housing_company_pictures(
    elastic_apartment: ElasticApartment,
) -> List[HousingCompanyPicture]:
    pictures = []

    main_image_url = getattr(elastic_apartment, "project_main_image_url", None)
    if main_image_url:
        pictures.append(
            HousingCompanyPicture(
                image_url=main_image_url,
            )
        )

    image_urls = getattr(elastic_apartment, "project_image_urls", None)
    if image_urls:
        for idx, picture_url in enumerate(image_urls):
            pictures.append(HousingCompanyPicture(image_url=picture_url))

    return pictures


def map_publication_time(time_value) -> Optional[date]:
    if time_value:
        return datetime.strptime(time_value, "%Y-%m-%dT%H:%M:%S%z")
    else:
        return None


def map_project_housing_company(elastic_apartment: ElasticApartment) -> str:
    project_housing_company = getattr(
        elastic_apartment, "project_housing_company", None
    )
    if project_housing_company:
        return project_housing_company
    else:
        raise ValueError(
            _("could not map the project_housing_company %s") % project_housing_company
        )


def map_oikotie_housing_company(
    elastic_apartment: ElasticApartment,
) -> HousingCompany:
    """
    Maps the ElasticSearch data to the Oikotie HousingCompany dataclass.
    """
    housing_company_field_dict = {
        "key": elastic_apartment.project_uuid,
        "name": map_project_housing_company(elastic_apartment),
        "real_estate_agent": map_real_estate_agent(elastic_apartment),
        "apartment": map_apartment(elastic_apartment),
        "address": map_address(elastic_apartment),
        "publication_start_date": map_publication_time(
            getattr(elastic_apartment, "project_publication_start_time", None)
        ),
        "publication_end_date": map_publication_time(
            getattr(elastic_apartment, "project_publication_end_time", None)
        ),
        "presentation_text": form_description(elastic_apartment),
        "coordinates": map_coordinates(elastic_apartment),
        "pictures": map_housing_company_pictures(elastic_apartment),
    }
    return HousingCompany(**housing_company_field_dict)
