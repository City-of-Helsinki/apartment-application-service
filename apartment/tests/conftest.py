import random
import string

import faker.config
from factory import Faker
from faker import providers
from pytest import fixture

from apartment.tests.factories import (
    ApartmentDocumentFactory,
    add_to_store,
    clear_apartment_store,
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
