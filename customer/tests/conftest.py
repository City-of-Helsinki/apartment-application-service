from pytest import fixture
from rest_framework.test import APIClient

from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@fixture
def api_client():
    return APIClient()


@fixture
def profile_api_client(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    return api_client
