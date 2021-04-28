from elasticsearch_dsl import Search
from time import sleep


def make_apartments_sold_in_elastic(elastic_apartments: list) -> None:
    for item in elastic_apartments:
        if item["apartment_state_of_sale"] == "FOR_SALE":
            item.delete()
    sleep(3)


def get_elastic_apartments_for_sale_uuids() -> list:
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale="FOR_SALE")
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
        .query("match", apartment_state_of_sale="FOR_SALE")
    )
    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(str(hit.project_uuid))
    return uuids
