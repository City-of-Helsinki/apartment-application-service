from uuid import UUID

from apartment.elastic.rest_client import DrupalSearchClient
from apartment.tests.factories import (
    get_apartments_from_store,
    get_project_from_store,
    get_projects_from_store,
)


class TestDrupalSearchClient(DrupalSearchClient):
    def get(self, path: str, params: dict = None, timeout=None) -> dict:
        """
        Mock get() method to return apartment/project data from APARTMENT_STORE
        or get_projects_from_store.
        """
        params = params or {}

        data = self._resolve_data(path, params)
        if data is None:
            return self._empty_response()

        data = self._apply_param_filters(data, params)
        return self._build_paginated_response(data, params)

    def _resolve_data(self, path: str, params: dict):
        stripped = path.rstrip("/")
        parts = stripped.split("/")
        if not parts:
            return None

        if parts[0] == "apartments":
            return self._resolve_apartment_path(parts, params)
        if parts[0] == "projects":
            return self._resolve_project_path(parts, params)
        return None

    def _resolve_apartment_path(self, parts, params):
        if len(parts) == 2:
            apartment_uuid = parts[1]
            apts = [
                a
                for a in get_apartments_from_store()
                if str(a.uuid) == str(apartment_uuid)
            ]
            return apts[:1] if apts else []
        return get_apartments_from_store(params.get("project_uuid"))

    def _resolve_project_path(self, parts, params):
        if len(parts) == 2:
            project_uuid = parts[1]
            try:
                return [get_project_from_store(project_uuid)]
            except KeyError:
                return []
        if len(parts) == 3 and parts[2] == "apartments":
            project_uuid = parts[1]
            return get_apartments_from_store(project_uuid)
        project_uuid = params.get("project_uuid")
        if project_uuid:
            try:
                return [get_project_from_store(project_uuid)]
            except KeyError:
                return []
        return get_projects_from_store()

    def _apply_param_filters(self, data, params: dict):
        def is_match(obj, key, value):
            attr = getattr(obj, key, None)
            if attr is None:
                return False
            if isinstance(attr, UUID):
                return str(attr) == str(value)
            return attr == value

        filtered = data
        for key, value in params.items():
            if key in {"limit", "offset"}:
                continue
            filtered = [obj for obj in filtered if is_match(obj, key, value)]
        return filtered

    def _build_paginated_response(self, data, params: dict):
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", len(data)))
        sliced = data[offset: offset + limit]
        hits = [{"_source": obj.__dict__} for obj in sliced]
        total = len(data)
        return {"hits": {"hits": hits, "total": {"value": total}}}

    def _empty_response(self):
        return {"hits": {"hits": [], "total": {"value": 0}}}
