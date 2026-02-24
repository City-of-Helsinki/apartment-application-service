from typing import Dict, Iterable, List, Optional, Tuple

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.rest_client import DrupalSearchClient


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
