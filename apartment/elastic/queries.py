from django.core.exceptions import ObjectDoesNotExist

from apartment.elastic.documents import ApartmentDocument


def get_apartment(apartment_uuid, include_project_fields=False):
    search = ApartmentDocument.search()

    # Filters
    search = search.filter("term", uuid__keyword=apartment_uuid)

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
    search = search.filter("term", uuid__keyword=apartment_uuid)
    search = search.source(includes=["project_uuid"])

    # Get item
    try:
        apartment = search.execute()[0]
    except IndexError:
        raise ObjectDoesNotExist("Apartment does not exist in ElasticSearch.")

    return apartment


def get_apartments(project_uuid=None):
    search = ApartmentDocument.search()

    # Filters
    if project_uuid:
        search = search.filter("term", project_uuid__keyword=project_uuid)

    # Exclude project fields
    search = search.source(excludes=["project_*"])

    # Get all items
    count = search.count()
    response = search[0:count].execute()

    return response


def get_apartment_uuids(project_uuid):
    search = ApartmentDocument.search()

    # Filters
    search = search.filter("term", project_uuid__keyword=project_uuid)

    # Include only apartment uuid and project uuid
    search = search.source(includes=["uuid", "project_uuid"])

    # Get all apartment uuids
    result = [hit.uuid for hit in search.scan()]

    return result


def get_project(project_uuid):
    search = ApartmentDocument.search()

    # Filters
    if project_uuid:
        search = search.filter("term", project_uuid__keyword=project_uuid)

    # Project data needs to exist in apartment data
    search = search.filter("exists", field="project_id")

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

    # Get all items
    count = search.count()
    response = search[0:count].execute()

    return response
