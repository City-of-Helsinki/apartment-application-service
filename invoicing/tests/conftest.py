import pytest
from rest_framework.test import APIClient

from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.fixture(autouse=True)
def settings_for_tests(settings):
    settings.SAP_SFTP_USERNAME = "test_sap_username"
    settings.SAP_SFTP_PASSWORD = "test_sap_password"
    settings.SAP_SFTP_HOST = "localhost"
    settings.SAP_SFTP_PORT = 22
    settings.SAP_SFTP_FILENAME_PREFIX = "test_sap_filename_prefix"


@pytest.fixture
def api_client():
    api_client = APIClient()
    return api_client


@pytest.fixture
def profile_api_client(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    return api_client
