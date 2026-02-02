import random
import string

import faker.config
from django.core.exceptions import ObjectDoesNotExist
from factory import Faker
from faker import providers
from pytest import fixture
from connections.tests.conftest import _mock_fetch_all

from apartment.tests.factories import (
    ApartmentDocumentFactory,
    add_to_store,
    clear_apartment_store,
    get_apartment_uuids_from_store,
    get_apartments_from_store,
    get_project_from_store,
    get_projects_from_store,
)
from users.tests.conftest import (  # noqa: F401
    api_client,
    drupal_salesperson_api_client,
    profile_api_client,
    sales_ui_salesperson_api_client,
    user_api_client,
)

faker.config.DEFAULT_LOCALE = "fi_FI"


class BusinessIdProvider(providers.BaseProvider):
    """Generates INVALID Finnish business ids in the format XXXXXXX-0
    where the X's are the seven digits and the 0 is the check digit.

    We use 0 as the check digit to avid clashing with any real company's business id
    (check digit 0 doesn't exist in the real world).
    """

    __provider__ = "business_id"

    def business_id(self) -> str:
        return "".join([random.choice(string.digits) for _ in range(7)]) + "-0"


Faker.add_provider(BusinessIdProvider)


@fixture(autouse=True)
def clear_store_between_tests():
    clear_apartment_store()
    yield
    clear_apartment_store()


@fixture(autouse=True)
def mock_apartment_queries(monkeypatch):


    def _get_apartments(project_uuid=None, include_project_fields=False):
        apartments = get_apartments_from_store(project_uuid)
        if include_project_fields:
            return apartments
        stripped = []
        for apartment in apartments:
            data = {
                key: value
                for key, value in apartment.__dict__.items()
                if not key.startswith("project_")
            }
            stripped.append(apartment.__class__(**data))
        return stripped

    def _get_projects():
        return get_projects_from_store()

    def _get_project(project_uuid):
        try:
            return get_project_from_store(project_uuid)
        except KeyError as exc:
            raise ObjectDoesNotExist("Project does not exist in REST API.") from exc

    def _get_apartment_uuids(project_uuid):
        return get_apartment_uuids_from_store(project_uuid)

    from apartment.api import views as apartment_views
    from apartment.elastic import queries

    monkeypatch.setattr(queries, "_fetch_all", _mock_fetch_all)



@fixture
def elasticsearch():
    clear_apartment_store()
    yield None
    clear_apartment_store()


@fixture
def elastic_apartments(elasticsearch):
    apartments = ApartmentDocumentFactory.create_batch(10)
    add_to_store(apartments)
    yield apartments


@fixture
def elastic_project_with_5_apartments(elasticsearch):
    apartments = []

    apartment = ApartmentDocumentFactory()
    apartments.append(apartment)

    for _ in range(4):
        apartments.append(ApartmentDocumentFactory(project_uuid=apartment.project_uuid))
    add_to_store(apartments)
    yield apartment.project_uuid, apartments
