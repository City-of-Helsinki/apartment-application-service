from typing import Dict, Iterable, List

from django.core.exceptions import ObjectDoesNotExist
from elasticsearch_dsl import search

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.elastic_utils import resolve_es_field


def apartment_query(**kwargs):
    search = _filter_apartments_with_keywords(**kwargs)
    count = search.count()
    response = search[0:count].execute()
    return response


def project_query(**kwargs):
    search = _filter_apartments_with_keywords(**kwargs)
    search = _filter_out_apartments(search)

    count = search.count()
    response = search[0:count].execute()
    return response


def get_apartment(apartment_uuid, include_project_fields=False):
    search = ApartmentDocument.search()

    # Filters
    search = search.filter("term", **{resolve_es_field("uuid"): apartment_uuid})

    if not include_project_fields:
        search = search.source(excludes=["project_*"])

    # Get item
    try:
        apartment = search.execute()[0]
    except IndexError:
        raise ObjectDoesNotExist("Apartment does not exist in ElasticSearch.")

    return apartment


def get_apartment_project_uuid(apartment_uuid):
    search = ApartmentDocument.search()

    # Filters
    search = search.filter("term", **{resolve_es_field("uuid"): apartment_uuid})
    search = search.source(includes=["project_uuid"])

    # Get item
    try:
        apartment = search.execute()[0]
    except IndexError:
        raise ObjectDoesNotExist("Apartment does not exist in ElasticSearch.")

    return apartment


def get_apartments(project_uuid=None, include_project_fields=False):
    search = ApartmentDocument.search()

    # Filters
    if project_uuid:
        search = search.filter(
            "term", **{resolve_es_field("project_uuid"): project_uuid}
        )

    # Exclude project fields if necessary
    if not include_project_fields:
        search = search.source(excludes=["project_*"])

    # Get all items
    count = search.count()
    response = search[0:count].execute()

    return response


def get_apartment_uuids(project_uuid) -> List[str]:
    search = ApartmentDocument.search()

    # Filters
    search = search.filter("term", **{resolve_es_field("project_uuid"): project_uuid})

    # Include only apartment uuid and project uuid
    search = search.source(includes=["uuid", "project_uuid"])

    # Get all apartment uuids
    result = [hit.uuid for hit in search.scan()]

    return result


def get_project(project_uuid):
    search = ApartmentDocument.search()

    # Filters
    if project_uuid:
        search = search.filter(
            "term", **{resolve_es_field("project_uuid"): project_uuid}
        )

    # Project data needs to exist in apartment data
    search = search.filter("exists", field="project_id")

    search = _filter_out_apartments(search)

    # Get only 1 item
    try:
        response = search.execute()[0]
    except IndexError:
        raise ObjectDoesNotExist("Project does not exist in ElasticSearch.")

    return response


def get_projects():
    search = ApartmentDocument.search()

    # Project data needs to exist in apartment data
    search = search.filter("exists", field="project_id")

    search = _filter_out_apartments(search)

    # Get all items
    count = search.count()
    response = search[0:count].execute()

    return response


def get_project_apartment_sale_state_counts(
    project_uuids: Iterable[str] = None,
) -> Dict[str, Dict[str, int]]:
    search = ApartmentDocument.search()

    if project_uuids is not None:
        project_uuids = list(project_uuids)
        if not project_uuids:
            return {}

        search = search.filter(
            "terms",
            **{resolve_es_field("project_uuid"): project_uuids},
        )

    projects_agg = search.aggs.bucket(
        "projects",
        "terms",
        field=resolve_es_field("project_uuid"),
        size=10000,
    )
    projects_agg.bucket(
        "states",
        "terms",
        field=resolve_es_field("apartment_state_of_sale"),
        size=20,
    )

    response = search[0:0].execute()

    counts_by_project_uuid = {}

    for project_bucket in response.aggregations.projects.buckets:
        sold_count = 0
        reserved_count = 0
        free_count = 0

        for state_bucket in project_bucket.states.buckets:
            state = state_bucket.key
            count = state_bucket.doc_count

            if state == "SOLD":
                sold_count += count
            elif state in {"RESERVED", "RESERVED_HASO"}:
                reserved_count += count
            elif state in {
                "FOR_SALE",
                "OPEN_FOR_APPLICATIONS",
                "FREE_FOR_RESERVATIONS",
            }:
                free_count += count

        counts_by_project_uuid[project_bucket.key] = {
            "sold_apartment_count": sold_count,
            "reserved_apartment_count": reserved_count,
            "free_apartment_count": free_count,
        }

    return counts_by_project_uuid


def _filter_apartments_with_keywords(**kwargs) -> search.Search:
    search = ApartmentDocument.search()
    for search_term, search_value in kwargs.items():
        if isinstance(search_value, str):
            search = search.filter(
                "term", **{resolve_es_field(search_term): search_value}
            )
        elif isinstance(search_value, bool):
            search = search.filter("term", **{search_term: search_value})

    return search


def _filter_out_apartments(search: search.Search) -> ApartmentDocument:
    """Filters out most recent Apartment which has project data

    Args:
        search (search.Search): _description_
    """
    # Get only most recent apartment which has project data
    search = search.extra(
        collapse={
            "field": "project_id",
            "inner_hits": {
                "name": "most_recent",
                "size": 1,
                "sort": [{"project_id": "desc"}],
            },
        }
    )

    # Retrieve only project fields
    search = search.source(["project_*"])

    return search
