import hashlib
import json
import logging
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

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

T = TypeVar("T")


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


def _drupal_cache_ttl() -> int:
    return settings.DRUPAL_SEARCH_API_CACHE_TTL


def _drupal_cache_key(*parts: str) -> str:
    return "drupal_search:v1:" + ":".join(parts)


def _drupal_cached(key: str, loader: Callable[[], T]) -> T:
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = loader()
    cache.set(key, value, timeout=_drupal_cache_ttl())
    return value


def _fetch_all_params_suffix(params: Dict) -> str:
    if not params:
        return "none"
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def _fetch_all_cache_key(path: str, params: Dict) -> str:
    return _drupal_cache_key("fetch_all", path, _fetch_all_params_suffix(params))


def _parse_hits(payload: Dict) -> Tuple[List[Dict], Optional[int]]:
    hits = payload.get("hits", {}).get("hits", [])
    total = payload.get("hits", {}).get("total", {}).get("value")
    sources = [hit.get("_source", {}) for hit in hits]
    return sources, total


def _fetch_all_uncached(path: str, params: Dict) -> List[Dict]:
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


def _fetch_all(path: str, params: Dict) -> List[Dict]:
    return _drupal_cached(
        _fetch_all_cache_key(path, params),
        lambda: _fetch_all_uncached(path, params),
    )


def _drupal_get_sources(path: str) -> List[Dict]:
    client = _get_client()
    try:
        payload = client.get(path)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise ObjectDoesNotExist(
                "Resource does not exist in Drupal search API."
            ) from e
        raise
    sources, _ = _parse_hits(payload)
    return sources


def _get_single_document(
    path: str,
    cache_key: str,
    *,
    include_project_fields: bool = False,
    not_found_message: str,
) -> SearchResult:
    def loader() -> SearchResult:
        sources = _drupal_get_sources(path)
        if not sources:
            raise ObjectDoesNotExist(not_found_message)
        return _to_results(sources[:1], include_project_fields=include_project_fields)[
            0
        ]

    return _drupal_cached(cache_key, loader)


def _parallel_fetch_unique(
    keys: Iterable[str],
    fetch: Callable[[str], T],
    *,
    max_workers: int = 8,
) -> Dict[str, T]:
    unique = list(dict.fromkeys(str(key) for key in keys))
    if not unique:
        return {}

    workers = min(len(unique), max_workers)
    result: Dict[str, T] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {executor.submit(fetch, key): key for key in unique}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            result[key] = future.result()
    return result


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


def apartment_query(**kwargs):
    sources = _fetch_all("apartments", params=kwargs)
    return _to_results(sources, include_project_fields=True)


def project_query(**kwargs):
    sources = _fetch_all("projects", params=kwargs)
    return _to_results(sources, include_project_fields=False)


def get_apartment(apartment_uuid, include_project_fields=False):
    """
    Fetch a single apartment by UUID via GET /apartments/{uuid}.

    Results are cached briefly (see DRUPAL_SEARCH_API_CACHE_TTL) to speed up
    repeated reads (e.g. multiple reservations for the same apartment).
    """
    uuid_str = str(apartment_uuid)
    cache_key = _drupal_cache_key(
        "apartment", uuid_str, str(int(include_project_fields))
    )
    return _get_single_document(
        f"apartments/{uuid_str}",
        cache_key,
        include_project_fields=include_project_fields,
        not_found_message="Apartment does not exist in Drupal search API.",
    )


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
    return _parallel_fetch_unique(
        apartment_uuids,
        lambda uuid_str: get_apartment(
            uuid_str, include_project_fields=include_project_fields
        ),
        max_workers=max_workers,
    )


def get_apartment_project_uuid(apartment_uuid):
    apartment = get_apartment(apartment_uuid, include_project_fields=True)
    return SearchResult({"project_uuid": apartment.project_uuid})


def get_apartments(project_uuid=None, include_project_fields=False, **filters):
    if project_uuid:
        sources = _fetch_all(f"projects/{str(project_uuid)}/apartments", params=filters)
    else:
        sources = _fetch_all("apartments", params=filters)
    return _to_results(sources, include_project_fields=include_project_fields)


def get_apartment_uuids_for_projects(
    project_uuids: Iterable[str],
    *,
    max_workers: int = 8,
) -> List[str]:
    """
    Resolve apartment UUIDs for many projects with bounded parallel HTTP.

    Each project triggers at most one ``get_apartment_uuids`` call (subject to
    cache). Duplicate project UUIDs are fetched once. Apartment UUIDs are
    de-duplicated (iteration order follows completion order and is not stable
    across runs).

    Parameters:
        project_uuids: Project UUID strings.
        max_workers: Upper bound on concurrent workers (capped by project count).

    Returns:
        List of unique apartment UUID strings across all given projects.
    """
    by_project = _parallel_fetch_unique(
        project_uuids, get_apartment_uuids, max_workers=max_workers
    )
    merged: List[str] = []
    for uuids in by_project.values():
        merged.extend(uuids)
    return list(dict.fromkeys(merged))


def get_apartment_uuids(project_uuid) -> List[str]:
    project_uuid_str = str(project_uuid)
    sources = _fetch_all(f"projects/{project_uuid_str}/apartments", params={})
    return [source.get("uuid") for source in sources if source.get("uuid")]


def get_projects_for_uuids(
    project_uuids: Iterable,
    *,
    max_workers: int = 8,
) -> List[SearchResult]:
    """
    Fetch many projects by UUID with bounded parallel HTTP requests.

    Each distinct UUID triggers at most one Drupal Search API GET via
    ``get_project`` (subject to its cache). Projects that no longer exist are
    omitted.

    Parameters:
        project_uuids: Project UUID values or strings to resolve.
        max_workers: Upper bound on concurrent workers (capped by unique count).

    Returns:
        List of project documents in the same order as the first occurrence of
        each UUID in ``project_uuids`` (missing projects are skipped).
    """
    unique = list(dict.fromkeys(str(u) for u in project_uuids))
    if not unique:
        return []

    def fetch(project_uuid: str) -> Optional[SearchResult]:
        try:
            return get_project(project_uuid)
        except ObjectDoesNotExist:
            return None

    by_uuid = _parallel_fetch_unique(unique, fetch, max_workers=max_workers)
    return [
        by_uuid[project_uuid]
        for project_uuid in unique
        if by_uuid.get(project_uuid) is not None
    ]


def get_project(project_uuid):
    """
    Fetch a single project by UUID via GET /projects/{uuid}.

    Results are cached briefly (see DRUPAL_SEARCH_API_CACHE_TTL) to speed up
    repeated reads (e.g. sales report selected projects).
    """
    uuid_str = str(project_uuid)
    cache_key = _drupal_cache_key("project", uuid_str)
    return _get_single_document(
        f"projects/{uuid_str}",
        cache_key,
        not_found_message="Project does not exist in Drupal search API.",
    )


def get_projects(**filters):
    sources = _fetch_all("projects", params=filters)
    return _to_results(sources, include_project_fields=False)


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
    apartment_uuid_to_project_uuid: Dict[str, str] = {}
    by_project = _parallel_fetch_unique(
        project_uuids_list, get_apartment_uuids, max_workers=8
    )
    for project_uuid, apartment_uuids in by_project.items():
        for apartment_uuid in apartment_uuids:
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
