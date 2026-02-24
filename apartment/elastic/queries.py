from typing import Dict, Iterable, List, Optional, Tuple

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.rest_client import DrupalSearchClient
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation


class SearchResult(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


_client: Optional[DrupalSearchClient] = None


def _get_client() -> DrupalSearchClient:
    global _client
    if _client is None:
        _client = DrupalSearchClient()
    return _client


def _parse_hits(payload: Dict) -> Tuple[List[Dict], Optional[int]]:
    hits = payload.get("hits", {}).get("hits", [])
    total = payload.get("hits", {}).get("total", {}).get("value")
    sources = [hit.get("_source", {}) for hit in hits]
    return sources, total


def _strip_project_fields(source: Dict) -> Dict:
    return {
        key: value for key, value in source.items() if not key.startswith("project_")
    }


def _fetch_all(path: str, params: Dict) -> List[Dict]:
    client = _get_client()
    sources: List[Dict] = []
    total: Optional[int] = None

    # When caller sets explicit limit (e.g. get_apartment), use simple path.
    if "limit" in params:
        offset = 0
        limit = int(params.get("limit", settings.DRUPAL_SEARCH_API_PAGE_SIZE))
        page_params = {**params, "offset": offset, "limit": limit}
        payload = client.get(path, params=page_params)
        page_sources, page_total = _parse_hits(payload)
        return page_sources

    # Adaptive pagination: try size=1000 with low timeout (cache probe).
    initial_size = 1000
    fallback_size = settings.DRUPAL_SEARCH_API_PAGE_SIZE
    initial_timeout = settings.DRUPAL_SEARCH_API_INITIAL_TIMEOUT
    full_timeout = settings.DRUPAL_SEARCH_API_TIMEOUT
    page_sources: List[Dict] = []
    limit = initial_size

    try:
        page_params = {**params, "limit": initial_size, "offset": 0}
        payload = client.get(path, params=page_params, timeout=initial_timeout)
        page_sources, total = _parse_hits(payload)
        sources.extend(page_sources)
        offset = initial_size
    except requests.exceptions.Timeout:
        try:
            payload = client.get(path, params=page_params, timeout=full_timeout)
            page_sources, total = _parse_hits(payload)
            sources.extend(page_sources)
            offset = initial_size
        except requests.exceptions.Timeout:
            limit = fallback_size
            page_params = {**params, "limit": fallback_size, "offset": 0}
            payload = client.get(path, params=page_params)
            page_sources, total = _parse_hits(payload)
            sources.extend(page_sources)
            offset = fallback_size

    while True:
        if total is not None and offset >= total:
            break
        if not page_sources or len(page_sources) < limit:
            break

        page_params = {**params, "limit": limit, "offset": offset}
        payload = client.get(path, params=page_params)
        page_sources, _ = _parse_hits(payload)
        sources.extend(page_sources)
        offset += limit

    return sources


def _to_results(
    sources: Iterable[Dict], include_project_fields: bool
) -> List[SearchResult]:
    results = []
    for source in sources:
        if not include_project_fields:
            source = _strip_project_fields(source)
        results.append(ApartmentDocument(**source))

    return results


def _to_project_results(sources: Iterable[Dict]) -> List[SearchResult]:
    return [ApartmentDocument(**source) for source in sources]


def apartment_query(**kwargs):
    sources = _fetch_all("apartments", params=kwargs)
    return _to_results(sources, include_project_fields=True)


def project_query(**kwargs):
    sources = _fetch_all("projects", params=kwargs)
    return _to_project_results(sources)


def get_apartment(apartment_uuid, include_project_fields=False):
    sources = _fetch_all(
        "apartments",
        params={"uuid": str(apartment_uuid), "limit": 1},
    )
    if not sources:
        raise ObjectDoesNotExist("Apartment does not exist in Drupal search API.")
    return _to_results(sources[:1], include_project_fields=include_project_fields)[0]


def get_apartment_project_uuid(apartment_uuid):
    apartment = get_apartment(apartment_uuid, include_project_fields=True)
    return SearchResult({"project_uuid": apartment.project_uuid})


def get_apartments(project_uuid=None, include_project_fields=False, **filters):
    if project_uuid:
        filters["project_uuid"] = str(project_uuid)
    sources = _fetch_all("apartments", params=filters)
    return _to_results(sources, include_project_fields=include_project_fields)


def get_apartment_uuids(project_uuid) -> List[str]:
    sources = _fetch_all(
        "apartments",
        params={"project_uuid": str(project_uuid)},
    )
    return [source.get("uuid") for source in sources if source.get("uuid")]


def get_project(project_uuid):
    sources = _fetch_all(
        "projects",
        params={"project_uuid": str(project_uuid), "limit": 1},
    )

    if not sources:
        raise ObjectDoesNotExist("Project does not exist in Drupal search API.")
    return _to_project_results(sources[:1])[0]


def get_projects(**filters):
    sources = _fetch_all("projects", params=filters)
    return _to_project_results(sources)


def get_project_apartment_sale_state_counts(
    project_uuids: Iterable[str],
) -> Dict[str, Dict[str, int]]:
    """
    Return per-project apartment sale state counts.

    Sale state is determined from the *winning* reservation (queue_position == 1),
    not from the apartment document's own sale state. This ensures that reservation
    workflow states override any lagging search index values.

    Parameters:
    project_uuids (Iterable[str]): Project UUIDs to calculate counts for.

    Returns:
    Dict[str, Dict[str, int]]: Mapping
        {project_uuid: {"sold_apartment_count": int,
                        "reserved_apartment_count": int,
                        "free_apartment_count": int}}
    """
    project_uuids_list = [str(u) for u in project_uuids]
    if not project_uuids_list:
        return {}

    apartment_uuid_to_project_uuid: Dict[str, str] = {}
    for project_uuid in project_uuids_list:
        for apartment in get_apartments(
            project_uuid=project_uuid,
            include_project_fields=True,
        ):
            apartment_uuid_to_project_uuid[str(apartment.uuid)] = str(project_uuid)

    if not apartment_uuid_to_project_uuid:
        return {
            project_uuid: {
                "sold_apartment_count": 0,
                "reserved_apartment_count": 0,
                "free_apartment_count": 0,
            }
            for project_uuid in project_uuids_list
        }

    # "Winning" here means the first reservation in the list for an apartment.
    # Queue positions are not always present (e.g. in some state transitions and
    # in tests), but list_position is always set.
    winning_reservations = (
        ApartmentReservation.objects.active()
        .filter(
            apartment_uuid__in=list(apartment_uuid_to_project_uuid.keys()),
            list_position=1,
        )
        .only("apartment_uuid", "state")
    )
    apartment_uuid_to_state = {
        str(r.apartment_uuid): r.state for r in winning_reservations
    }

    counts: Dict[str, Dict[str, int]] = {
        project_uuid: {
            "sold_apartment_count": 0,
            "reserved_apartment_count": 0,
            "free_apartment_count": 0,
        }
        for project_uuid in project_uuids_list
    }

    for apartment_uuid, project_uuid in apartment_uuid_to_project_uuid.items():
        state = apartment_uuid_to_state.get(apartment_uuid)

        if state == ApartmentReservationState.SOLD:
            counts[project_uuid]["sold_apartment_count"] += 1
        elif state is None or state == ApartmentReservationState.SUBMITTED:
            counts[project_uuid]["free_apartment_count"] += 1
        else:
            counts[project_uuid]["reserved_apartment_count"] += 1

    return counts
