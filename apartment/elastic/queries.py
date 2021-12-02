from elasticsearch_dsl import Q

from apartment.elastic.documents import ApartmentDocument


def get_projects():
    # Project data needs to exist in apartment data
    query = Q("bool", must=Q("exists", field="project_id"))
    search = ApartmentDocument.search().query(query)

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

    response = search.execute()
    return response
