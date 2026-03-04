from collections import defaultdict
from typing import Dict, Iterable, List

from django.core.exceptions import ObjectDoesNotExist
from elasticsearch_dsl import search

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.elastic_utils import resolve_es_field
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation


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

    project_uuid_list = None
    if project_uuids is not None:
        project_uuid_list = list(project_uuids)
        if not project_uuid_list:
            return {}

        search = search.filter(
            "terms",
            **{resolve_es_field("project_uuid"): project_uuid_list},
        )

    search = search.source(includes=["uuid", "project_uuid"])

    apartment_uuids_by_project = defaultdict(list)
    for apartment in search.scan():
        apartment_uuids_by_project[str(apartment.project_uuid)].append(
            str(apartment.uuid)
        )

    apartment_uuids = [
        apartment_uuid
        for project_apartment_uuids in apartment_uuids_by_project.values()
        for apartment_uuid in project_apartment_uuids
    ]

    apartment_reservation_states = defaultdict(list)
    reservation_rows = (
        ApartmentReservation.objects.active()
        .exclude(state=ApartmentReservationState.SUBMITTED)
        .filter(apartment_uuid__in=apartment_uuids)
        .values_list("apartment_uuid", "state")
    )
    for apartment_uuid, reservation_state in reservation_rows:
        apartment_reservation_states[str(apartment_uuid)].append(reservation_state)

    counts_by_project_uuid = {}
    for project_uuid, project_apartment_uuids in apartment_uuids_by_project.items():
        sold_count = 0
        reserved_count = 0
        free_count = 0
        review_count = 0
        reservation_agreement_count = 0
        offered_count = 0
        offer_accepted_count = 0
        offer_expired_count = 0
        accepted_by_municipality_count = 0

        for apartment_uuid in project_apartment_uuids:
            reservation_states = apartment_reservation_states.get(apartment_uuid, [])

            if len(reservation_states) == 0:
                free_count += 1
                continue

            if len(reservation_states) == 1 and reservation_states[0] in {
                ApartmentReservationState.SOLD,
                ApartmentReservationState.SOLD.value,
            }:
                sold_count += 1
                continue

            if len(reservation_states) > 1:
                review_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.REVIEW,
                ApartmentReservationState.REVIEW.value,
            }:
                review_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.RESERVED,
                ApartmentReservationState.RESERVED.value,
            }:
                reserved_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.RESERVATION_AGREEMENT,
                ApartmentReservationState.RESERVATION_AGREEMENT.value,
            }:
                reservation_agreement_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.OFFERED,
                ApartmentReservationState.OFFERED.value,
            }:
                offered_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.OFFER_ACCEPTED,
                ApartmentReservationState.OFFER_ACCEPTED.value,
            }:
                offer_accepted_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.OFFER_EXPIRED,
                ApartmentReservationState.OFFER_EXPIRED.value,
            }:
                offer_expired_count += 1
                continue

            if reservation_states[0] in {
                ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY,
                ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY.value,
            }:
                accepted_by_municipality_count += 1
                continue

            review_count += 1

        counts_by_project_uuid[project_uuid] = {
            "sold_apartment_count": sold_count,
            "reserved_apartment_count": reserved_count,
            "free_apartment_count": free_count,
            "review_apartment_count": review_count,
            "reservation_agreement_apartment_count": reservation_agreement_count,
            "offered_apartment_count": offered_count,
            "offer_accepted_apartment_count": offer_accepted_count,
            "offer_expired_apartment_count": offer_expired_count,
            "accepted_by_municipality_apartment_count": (
                accepted_by_municipality_count
            ),
        }

    if project_uuid_list is not None:
        for project_uuid in project_uuid_list:
            counts_by_project_uuid.setdefault(
                str(project_uuid),
                {
                    "sold_apartment_count": 0,
                    "reserved_apartment_count": 0,
                    "free_apartment_count": 0,
                    "review_apartment_count": 0,
                    "reservation_agreement_apartment_count": 0,
                    "offered_apartment_count": 0,
                    "offer_accepted_apartment_count": 0,
                    "offer_expired_apartment_count": 0,
                    "accepted_by_municipality_apartment_count": 0,
                },
            )

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
