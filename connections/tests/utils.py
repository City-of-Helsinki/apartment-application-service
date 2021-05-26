from elasticsearch_dsl import Search
from time import sleep

from connections.enums import ApartmentStateOfSale


def make_apartments_sold_in_elastic() -> None:
    s_obj = Search(index="test-apartment").query(
        "match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE
    )
    s_obj.delete()
    sleep(3)


def get_elastic_apartments_for_sale_uuids() -> list:
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
    )
    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(str(hit.uuid))
    return uuids


def get_elastic_apartments_for_sale_project_uuids() -> list:
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
    )
    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(str(hit.project_uuid))
    return uuids
