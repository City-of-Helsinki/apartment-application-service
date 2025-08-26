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


def get_apartment_uuids(project_uuid):
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
