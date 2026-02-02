from uuid import UUID

from apartment.elastic.rest_client import DrupalSearchClient
from apartment.tests.factories import (
    get_apartments_from_store,
    get_project_from_store,
    get_projects_from_store,
)

class TestDrupalSearchClient(DrupalSearchClient):
    def get(self, path: str, params: dict = None) -> dict:
        """
        Mock get() method to return apartment/project data from APARTMENT_STORE or get_projects_from_store.
        """

        params = params or {}
        data = []


        if path.rstrip("/") == "apartments":
            data = get_apartments_from_store(params.get("project_uuid"))
        elif path.rstrip("/") == "projects":
            if project_uuid := params.get("project_uuid"):
                try:
                    data = [get_project_from_store(project_uuid)]
                except KeyError:
                    data = []
            else:
                data = get_projects_from_store()
        else:
            return {"hits": {"hits": [], "total": {"value": 0}}}

        # Filter by params (ignore pagination keys)
        for key, value in params.items():
            if key in ("limit", "offset"):
                continue

            def _matches(obj):
                attr = getattr(obj, key, None)
                if attr is None:
                    return False
                if isinstance(attr, UUID):
                    return str(attr) == str(value)
                return attr == value

            data = [d for d in data if _matches(d)]

        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", len(data)))
        page = data[offset : offset + limit]
        hits = [{"_source": obj.__dict__} for obj in page]
        total = len(data)
        return {
            "hits": {
                "hits": hits,
                "total": {"value": total}
            }
        }

