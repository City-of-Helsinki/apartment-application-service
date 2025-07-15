import random
import string
from factory import Faker
from faker import providers
import faker.config
from django.conf import settings
from elasticsearch.helpers.test import get_test_client
from elasticsearch_dsl.connections import add_connection
from pytest import fixture

from apartment.tests.factories import ApartmentDocumentFactory
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


def setup_elasticsearch():
    test_client = get_test_client()
    add_connection("default", test_client)
    if test_client.indices.exists(index=settings.APARTMENT_INDEX_NAME):
        test_client.indices.delete(index=settings.APARTMENT_INDEX_NAME)
    test_client.indices.create(index=settings.APARTMENT_INDEX_NAME)
    return test_client


def teardown_elasticsearch(test_client):
    if test_client.indices.exists(index=settings.APARTMENT_INDEX_NAME):
        test_client.indices.delete(index=settings.APARTMENT_INDEX_NAME)


@fixture(scope="module")
def elasticsearch():
    test_client = setup_elasticsearch()
    yield test_client
    teardown_elasticsearch(test_client)


@fixture
def elastic_apartments(elasticsearch):
    apartments = ApartmentDocumentFactory.create_batch(10)
    yield apartments
    for apartment in apartments:
        apartment.delete(refresh=True)


@fixture
def elastic_project_with_5_apartments(elasticsearch):
    apartments = []

    apartment = ApartmentDocumentFactory()
    apartments.append(apartment)

    for _ in range(4):
        apartments.append(ApartmentDocumentFactory(project_uuid=apartment.project_uuid))
    yield apartment.project_uuid, apartments

    for apartment in apartments:
        apartment.delete(refresh=True)
