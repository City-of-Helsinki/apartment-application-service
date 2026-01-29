import importlib
from typing import Iterable

import pytest
from django.core.exceptions import ObjectDoesNotExist

from apartment.tests.factories import (
    ApartmentData,
    APARTMENT_STORE,
    clear_apartment_store,
    get_apartment_uuids_from_store,
    get_apartments_from_store,
    get_project_from_store,
    get_projects_from_store,
)


@pytest.fixture(autouse=True)
def clear_store_between_tests():
    clear_apartment_store()
    yield
    clear_apartment_store()


@pytest.fixture(autouse=True)
def mock_search_api(monkeypatch):
    def _get_apartments(project_uuid=None, include_project_fields=False, **filters):
        apartments = list(get_apartments_from_store(project_uuid))
        for key, value in filters.items():
            if isinstance(value, (str, bool, int, float)):
                apartments = [apt for apt in apartments if getattr(apt, key) == value]
        if include_project_fields:
            return apartments
        stripped = []
        for apartment in apartments:
            data = {
                key: value
                for key, value in apartment.__dict__.items()
                if not key.startswith("project_")
            }
            stripped.append(ApartmentData(**data))
        return stripped

    def _get_apartment(apartment_uuid, include_project_fields=False):
        for apartment in APARTMENT_STORE:
            if str(apartment.uuid) == str(apartment_uuid):
                if include_project_fields:
                    return apartment
                data = {
                    key: value
                    for key, value in apartment.__dict__.items()
                    if not key.startswith("project_")
                }
                return ApartmentData(**data)
        raise ObjectDoesNotExist("Apartment does not exist in REST API.")

    def _get_project(project_uuid):
        try:
            return get_project_from_store(project_uuid)
        except KeyError as exc:
            raise ObjectDoesNotExist("Project does not exist in REST API.") from exc

    def _get_projects():
        return get_projects_from_store()

    def _get_apartment_uuids(project_uuid):
        return get_apartment_uuids_from_store(project_uuid)

    def _apartment_query(**kwargs):
        return _get_apartments(**kwargs)

    from apartment.elastic import queries

    monkeypatch.setattr(queries, "get_apartment", _get_apartment)
    monkeypatch.setattr(queries, "get_apartments", _get_apartments)
    monkeypatch.setattr(queries, "get_project", _get_project)
    monkeypatch.setattr(queries, "get_projects", _get_projects)
    monkeypatch.setattr(queries, "get_apartment_uuids", _get_apartment_uuids)
    monkeypatch.setattr(queries, "apartment_query", _apartment_query)

    module_patch_map = {
        "apartment.api.views": [
            "get_apartment_uuids",
            "get_apartments",
            "get_project",
            "get_projects",
        ],
        "apartment.api.serializers": ["get_apartments"],
        "apartment.services": ["get_apartment"],
        "apartment.utils": ["get_apartment"],
        "application_form.api.serializers": ["get_apartment_uuids", "get_project"],
        "application_form.api.views": ["get_apartment_uuids"],
        "application_form.api.sales.serializers": ["get_apartment"],
        "application_form.api.sales.views": ["get_apartment", "get_project"],
        "application_form.services.application": ["get_apartment"],
        "application_form.services.reservation": ["get_apartment"],
        "application_form.services.offer": ["get_apartment", "get_apartment_uuids"],
        "application_form.services.queue": ["get_apartment"],
        "application_form.services.export": [
            "get_apartment",
            "get_apartment_uuids",
            "get_apartments",
            "get_project",
            "get_projects",
        ],
        "application_form.services.lottery.utils": [
            "get_apartment_uuids",
            "get_project",
        ],
        "application_form.services.lottery.haso": ["get_apartment_uuids"],
        "application_form.services.lottery.hitas": [
            "get_apartment",
            "get_apartment_uuids",
        ],
        "application_form.services.lottery.machine": ["get_project"],
        "application_form.validators": ["get_apartment_uuids", "get_project"],
        "application_form.pdf.hitas": ["get_apartment"],
        "application_form.pdf.haso": ["get_apartment"],
        "application_form.tests.conftest": [
            "get_apartment",
            "get_apartment_uuids",
            "get_apartments",
            "get_project",
            "get_projects",
        ],
        "application_form.tests.test_queue_services": ["get_apartment"],
        "application_form.tests.test_export_service": [
            "get_apartment",
            "get_apartment_uuids",
            "get_apartments",
            "get_project",
        ],
        "invoicing.api.serializers": ["get_project"],
        "invoicing.api.views": ["get_apartment"],
        "invoicing.pdf": ["get_apartment", "get_project"],
        "invoicing.sap.send.xml_utils": ["get_apartment"],
        "cost_index.api.views": ["get_apartment"],
        "customer.api.sales.serializers": ["get_apartment"],
        "asko_import.describer": ["get_apartment", "get_project"],
    }

    replacements = {
        "get_apartment": _get_apartment,
        "get_apartments": _get_apartments,
        "get_project": _get_project,
        "get_projects": _get_projects,
        "get_apartment_uuids": _get_apartment_uuids,
        "apartment_query": _apartment_query,
    }

    def _patch_module(module_path: str, names: Iterable[str]):
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            return
        for name in names:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, replacements[name])

    for module_path, names in module_patch_map.items():
        _patch_module(module_path, names)
