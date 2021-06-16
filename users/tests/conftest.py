import faker.config
import pytest
from rest_framework.test import APIClient

from users.tests.utils import _create_profile

faker.config.DEFAULT_LOCALE = "fi_FI"

PROFILE_TEST_DATA = {
    "id": "f12882ee-c7a9-46da-9233-b66b0ea7d66f",
    "first_name": "Mikko",
    "last_name": "Mallikas",
    "email": "example@example.com",
    "phone_number": "+358123456789",
    "street_address": "Mannerheiminkatu 3",
    "city": "Helsinki",
    "postal_code": "00100",
    "date_of_birth": "1980-01-25",
    "contact_language": "fi",
}

OTHER_PROFILE_TEST_DATA = {
    **PROFILE_TEST_DATA,
    "id": "872e8f85-e23a-42ed-9364-c3620c190d98",
}

TEST_USER_PASSWORD = "test password"


@pytest.fixture
def profile():
    return _create_profile(PROFILE_TEST_DATA, TEST_USER_PASSWORD)


@pytest.fixture
def other_profile():
    return _create_profile(OTHER_PROFILE_TEST_DATA, TEST_USER_PASSWORD)


@pytest.fixture
def api_client():
    return APIClient()
