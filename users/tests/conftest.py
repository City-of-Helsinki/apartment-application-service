import faker.config
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from users.enums import Roles
from users.tests.factories import ProfileFactory, UserFactory
from users.tests.utils import _create_profile, _create_token

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


@pytest.fixture
def profile_api_client():
    api_client = APIClient()
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    return api_client


@pytest.fixture
def user_api_client():
    user = UserFactory()
    api_client = APIClient()
    api_client.force_authenticate(user)
    api_client.user = user
    return api_client


@pytest.fixture
def drupal_salesperson_api_client():
    user = UserFactory()
    api_client = APIClient()
    api_client.force_authenticate(user)
    # Drupal salespersons have a profile contrary to sales UI salespersons
    ProfileFactory(user=user)
    api_client.user = user
    Group.objects.get(name__iexact=Roles.SALESPERSON.name).user_set.add(user)
    return api_client


@pytest.fixture
def sales_ui_salesperson_api_client():
    user = UserFactory()
    api_client = APIClient()
    api_client.force_authenticate(user)
    api_client.user = user
    Group.objects.get(name__iexact=Roles.SALESPERSON.name).user_set.add(user)
    return api_client
