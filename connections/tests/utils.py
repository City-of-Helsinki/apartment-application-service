from django.conf import settings
from elasticsearch_dsl import Search, UpdateByQuery
from elasticsearch_dsl.connections import get_connection

from apartment.elastic.documents import ApartmentDocument
from connections.enums import ApartmentStateOfSale


def make_apartments_sold_in_elastic() -> None:
    s_obj = ApartmentDocument.search().query(
        "match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE
    )
    s_obj.delete()

    get_connection().indices.refresh(index=settings.APARTMENT_INDEX_NAME)


def get_elastic_apartments_for_sale_published_on_etuovi_uuids(
    only_etuovi_published=False,
) -> list:
    """
    Get apartments for sale and published only on Etuovi
    If oikotie_published is False exclude apartments published on Oikotie
    """
    s_obj = (
        ApartmentDocument.search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
        .query("match", publish_on_etuovi=True)
    )
    if only_etuovi_published:
        s_obj = s_obj.query("match", publish_on_oikotie=False)

    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(hit.uuid)
    return uuids


def get_elastic_apartments_for_sale_published_on_oikotie_uuids(
    only_oikotie_published=False,
) -> list:
    """
    Get apartments for sale and published on Oikotie
    If etuovi_published is False exclude apartments published on Etuovi
    """
    s_obj = (
        ApartmentDocument.search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
        .query("match", publish_on_oikotie=True)
    )
    if only_oikotie_published:
        s_obj = s_obj.query("match", publish_on_etuovi=False)

    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(hit.uuid)
    return uuids


def get_elastic_apartments_for_sale_published_uuids() -> list:
    """
    Get apartments for sale and published both on Oikotie and Etuovi
    """
    s_obj = (
        ApartmentDocument.search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
        .query("match", publish_on_etuovi=True)
        .query("match", publish_on_oikotie=True)
    )

    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(hit.uuid)
    return uuids


def get_elastic_apartments_for_sale_only_uuids() -> list:
    """
    Get apartments only for sale but not to published
    """
    s_obj = (
        ApartmentDocument.search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
        .query("match", publish_on_etuovi=False)
        .query("match", publish_on_oikotie=False)
    )

    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(hit.uuid)
    return uuids


def get_elastic_apartments_not_for_sale():
    """
    Get apartments not for sale but with published flags
    """
    s_obj = (
        ApartmentDocument.search()
        .query("match", publish_on_oikotie=True)
        .query("match", publish_on_etuovi=True)
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.RESERVED)
    )
    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(hit.uuid)
    return uuids


def get_elastic_apartments_for_sale_project_uuids() -> list:
    """Used only in oikotie tests for fetching expected housing companies"""
    s_obj = (
        ApartmentDocument.search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
        .query("match", publish_on_oikotie=True)
    )
    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    for hit in scan:
        uuids.append(str(hit.project_uuid))
    return uuids


def publish_elastic_apartments(
    uuids: list, publish_to_etuovi=False, publish_to_oikotie=False
) -> list:
    """
    Sets flags publish_on_oikotie or/and publish_on_etuovi to true
    for apartments in elasticsearch provided as list of uuids
    """
    u_obj = UpdateByQuery(
        index=settings.APARTMENT_INDEX_NAME,
    ).query("multi_match", query=" ".join(uuids), fields=["uuid"])

    if publish_to_etuovi and publish_to_oikotie:
        u_obj = u_obj.script(
            source="ctx._source.publish_on_oikotie = true; "
            "ctx._source.publish_on_etuovi = true"
        )
    elif publish_to_oikotie:
        u_obj = u_obj.script(source="ctx._source.publish_on_oikotie = true")
    elif publish_to_etuovi:
        u_obj = u_obj.script(source="ctx._source.publish_on_etuovi = true")
    u_obj.execute()

    get_connection().indices.refresh(index=settings.APARTMENT_INDEX_NAME)

    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
    )
    if publish_to_oikotie:
        s_obj = s_obj.query("match", publish_on_oikotie=publish_to_oikotie)
    if publish_to_etuovi:
        s_obj = s_obj.query("match", publish_on_etuovi=publish_to_etuovi)
    scan = s_obj.scan()
    uuids = []

    for hit in scan:
        uuids.append(hit.uuid)
    return uuids


def unpublish_elastic_oikotie_apartments(uuids: list) -> list:
    """
    Sets flag publish_on_oikotieto to false for apartments
    in elasticsearch provided as list of uuids
    """
    u_obj = UpdateByQuery(
        index=settings.APARTMENT_INDEX_NAME,
    ).query("multi_match", query=" ".join(uuids), fields=["uuid"])

    u_obj = u_obj.script(source="ctx._source.publish_on_oikotie = false")
    u_obj.execute()

    get_connection().indices.refresh(index=settings.APARTMENT_INDEX_NAME)
