import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from pydantic import ValidationError

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.rest_client import DrupalSearchClient
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation

logger = logging.getLogger(__name__)


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


def _validate_document(source: Dict) -> ApartmentDocument:
    """
    Validate a single Drupal _source dict into an ApartmentDocument.

    ValidationErrors are re-raised so callers/tests see real data problems,
    but we first log the offending document's uuid/project_uuid to make the
    root cause traceable in production logs.
    """
    try:
        return ApartmentDocument.model_validate(source)
    except ValidationError:
        logger.error(
            "ApartmentDocument validation failed " "(uuid=%s, project_uuid=%s)",
            source.get("uuid"),
            source.get("project_uuid"),
        )
        raise


def _to_results(
    sources: Iterable[Dict], include_project_fields: bool
) -> List[SearchResult]:
    return [_validate_document(source) for source in sources]


def _to_project_results(sources: Iterable[Dict]) -> List[SearchResult]:
    return [_validate_document(source) for source in sources]


def apartment_query(**kwargs):
    sources = _fetch_all("apartments", params=kwargs)
    return _to_results(sources, include_project_fields=True)


def project_query(**kwargs):
    sources = _fetch_all("projects", params=kwargs)
    return _to_project_results(sources)


def get_apartment(apartment_uuid, include_project_fields=False):
    """
    Fetch a single apartment by UUID via GET /apartments/{uuid}.

    Results are cached briefly (see DRUPAL_SEARCH_API_CACHE_TTL) to speed up
    repeated reads (e.g. multiple reservations for the same apartment).
    """
    uuid_str = str(apartment_uuid)
    cache_key = f"drupal_search:apartment:v1:{uuid_str}:{int(include_project_fields)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = _get_client()
    try:
        payload = client.get(f"apartments/{uuid_str}")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise ObjectDoesNotExist(
                "Apartment does not exist in Drupal search API."
            ) from e
        raise
    sources, _ = _parse_hits(payload)
    if not sources:
        raise ObjectDoesNotExist("Apartment does not exist in Drupal search API.")
    result = _to_results(sources[:1], include_project_fields=include_project_fields)[0]
    ttl = settings.DRUPAL_SEARCH_API_CACHE_TTL
    cache.set(cache_key, result, timeout=ttl)
    return result


def get_apartments_for_uuids(
    apartment_uuids: Iterable,
    *,
    include_project_fields: bool = False,
    max_workers: int = 8,
) -> Dict[str, ApartmentDocument]:
    """
    Fetch many apartments by UUID with bounded parallel HTTP requests.

    Each distinct UUID triggers at most one Drupal Search API GET (subject
    to get_apartment's cache). Duplicate UUIDs in ``apartment_uuids`` share
    a single fetch.

    Parameters:
        apartment_uuids: UUID values or strings to resolve.
        include_project_fields: Passed through to ``get_apartment``.
        max_workers: Upper bound on concurrent workers (capped by unique count).

    Returns:
        Mapping ``str(uuid) -> apartment document`` (same type as
        ``get_apartment`` return value).
    """
    unique = list(dict.fromkeys(str(u) for u in apartment_uuids))
    if not unique:
        return {}

    workers = min(len(unique), max_workers)

    def _fetch(uuid_str: str) -> Tuple[str, ApartmentDocument]:
        doc = get_apartment(
            uuid_str, include_project_fields=include_project_fields
        )
        return uuid_str, doc

    result: Dict[str, ApartmentDocument] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch, u) for u in unique]
        for future in as_completed(futures):
            key, value = future.result()
            result[key] = value
    return result


def get_apartment_project_uuid(apartment_uuid):
    apartment = get_apartment(apartment_uuid, include_project_fields=True)
    return SearchResult({"project_uuid": apartment.project_uuid})


def get_apartments(project_uuid=None, include_project_fields=False, **filters):
    if project_uuid:
        sources = _fetch_all(f"projects/{str(project_uuid)}/apartments", params=filters)
    else:
        sources = _fetch_all("apartments", params=filters)
    return _to_results(sources, include_project_fields=include_project_fields)


def get_apartment_uuids(project_uuid) -> List[str]:
    project_uuid_str = str(project_uuid)
    cache_key = f"drupal_search:project_apartment_uuids:v1:{project_uuid_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(
            "get_apartment_uuids: cached project apartment uuids for project %s",
            project_uuid_str,
        )
        return cached

    sources = _fetch_all(f"projects/{project_uuid_str}/apartments", params={})
    uuids = [source.get("uuid") for source in sources if source.get("uuid")]

    timeout = settings.DRUPAL_SEARCH_API_CACHE_TTL
    cache.set(cache_key, uuids, timeout=timeout)
    return uuids


def get_project(project_uuid):
    """Fetch a single project by UUID via GET /projects/{uuid}."""
    client = _get_client()
    try:
        payload = client.get(f"projects/{str(project_uuid)}")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise ObjectDoesNotExist(
                "Project does not exist in Drupal search API."
            ) from e
        raise
    sources, _ = _parse_hits(payload)
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

    counts: Dict[str, Dict[str, int]] = {
        project_uuid: {
            "sold_apartment_count": 0,
            "reserved_apartment_count": 0,
            "free_apartment_count": 0,
        }
        for project_uuid in project_uuids_list
    }

    # Each lookup is an HTTP round trip to the Drupal search API. Fan them out
    # concurrently so total runtime is bounded by the slowest request rather
    # than the sum of all requests. Workers are capped to avoid overwhelming
    # the backend on large project sets.
    max_workers = min(len(project_uuids_list), 8)
    apartment_uuid_to_project_uuid: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_project = {
            executor.submit(get_apartment_uuids, project_uuid): project_uuid
            for project_uuid in project_uuids_list
        }
        for future, project_uuid in future_to_project.items():
            for apartment_uuid in future.result():
                apartment_uuid_to_project_uuid[str(apartment_uuid)] = project_uuid

    if not apartment_uuid_to_project_uuid:
        return counts

    # "Winning" here means the first reservation in the list for an apartment.
    # Queue positions are not always present (e.g. in some state transitions and
    # in tests), but list_position is always set.
    winning_reservations = (
        ApartmentReservation.objects.active()
        .filter(
            apartment_uuid__in=list(apartment_uuid_to_project_uuid.keys()),
            list_position=1,
        )
        .values_list("apartment_uuid", "state")
    )
    apartment_uuid_to_state = {str(uuid): state for uuid, state in winning_reservations}

    for apartment_uuid, project_uuid in apartment_uuid_to_project_uuid.items():
        state = apartment_uuid_to_state.get(apartment_uuid)

        if state == ApartmentReservationState.SOLD:
            counts[project_uuid]["sold_apartment_count"] += 1
        elif state is None or state == ApartmentReservationState.SUBMITTED:
            counts[project_uuid]["free_apartment_count"] += 1
        else:
            counts[project_uuid]["reserved_apartment_count"] += 1

    return counts
