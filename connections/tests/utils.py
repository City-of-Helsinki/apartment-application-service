from apartment.tests.factories import APARTMENT_STORE
from connections.enums import ApartmentStateOfSale


def make_apartments_sold_in_elastic() -> None:
    for apartment in APARTMENT_STORE:
        if apartment.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE:
            apartment.apartment_state_of_sale = ApartmentStateOfSale.SOLD


def get_elastic_apartments_for_sale_published_on_etuovi_uuids(
    only_etuovi_published=False,
) -> list:
    """
    Get apartments for sale and published only on Etuovi
    If oikotie_published is False exclude apartments published on Oikotie
    """
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
        and apt.publish_on_etuovi is True
    ]
    if only_etuovi_published:
        apartments = [apt for apt in apartments if apt.publish_on_oikotie is False]
    return [apt.uuid for apt in apartments]


def get_elastic_apartments_not_sold_published_on_oikotie_uuids(
    only_oikotie_published=False,
) -> list:
    """
    Get apartments where apartment_state_of_sale != "SOLD" and published on Oikotie
    If etuovi_published is False exclude apartments published on Etuovi
    """
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale != ApartmentStateOfSale.SOLD
        and apt.publish_on_oikotie is True
    ]
    if only_oikotie_published:
        apartments = [apt for apt in apartments if apt.publish_on_etuovi is False]
    return [apt.uuid for apt in apartments]


def get_elastic_apartments_for_sale_published_on_oikotie_uuids(
    only_oikotie_published=False,
) -> list:
    """
    Get apartments for sale and published on Oikotie
    If etuovi_published is False exclude apartments published on Etuovi
    """
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
        and apt.publish_on_oikotie is True
    ]
    if only_oikotie_published:
        apartments = [apt for apt in apartments if apt.publish_on_etuovi is False]
    return [apt.uuid for apt in apartments]


def get_elastic_apartments_for_sale_published_uuids() -> list:
    """
    Get apartments for sale and published both on Oikotie and Etuovi
    """
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
        and apt.publish_on_etuovi is True
        and apt.publish_on_oikotie is True
    ]
    return [apt.uuid for apt in apartments]


def get_elastic_apartments_for_sale_only_uuids() -> list:
    """
    Get apartments only for sale but not to published
    """
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
        and apt.publish_on_etuovi is False
        and apt.publish_on_oikotie is False
    ]
    return [apt.uuid for apt in apartments]


def get_elastic_apartments_not_for_sale():
    """
    Get apartments not for sale but with published flags
    """
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt.publish_on_oikotie is True
        and apt.publish_on_etuovi is True
        and apt.apartment_state_of_sale == ApartmentStateOfSale.RESERVED
    ]
    return [apt.uuid for apt in apartments]


def get_elastic_apartments_for_sale_project_uuids() -> list:
    """Used only in oikotie tests for fetching expected housing companies"""
    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
        and apt.publish_on_oikotie is True
    ]
    return [str(apt.project_uuid) for apt in apartments]


def publish_elastic_apartments(
    uuids: list, publish_to_etuovi=False, publish_to_oikotie=False
) -> list:
    """
    Sets flags publish_on_oikotie or/and publish_on_etuovi to true
    for apartments in elasticsearch provided as list of uuids
    """
    for apartment in APARTMENT_STORE:
        if apartment.uuid not in uuids:
            continue
        if publish_to_etuovi:
            apartment.publish_on_etuovi = True
        if publish_to_oikotie:
            apartment.publish_on_oikotie = True

    apartments = [
        apt
        for apt in APARTMENT_STORE
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
    ]
    if publish_to_oikotie:
        apartments = [apt for apt in apartments if apt.publish_on_oikotie]
    if publish_to_etuovi:
        apartments = [apt for apt in apartments if apt.publish_on_etuovi]
    return [apt.uuid for apt in apartments]


def unpublish_elastic_oikotie_apartments(uuids: list) -> list:
    """
    Sets flag publish_on_oikotieto to false for apartments
    in elasticsearch provided as list of uuids
    """
    for apartment in APARTMENT_STORE:
        if apartment.uuid in uuids:
            apartment.publish_on_oikotie = False
