import pytest

from users.tests.conftest import api_client, user_api_client  # noqa: F401


@pytest.fixture(autouse=True)
def settings_for_tests(settings):
    settings.SAP_SFTP_USERNAME = "test_sap_username"
    settings.SAP_SFTP_PASSWORD = "test_sap_password"
    settings.SAP_SFTP_HOST = "localhost"
    settings.SAP_SFTP_PORT = 22
    settings.SAP_SFTP_FILENAME_PREFIX = "test_sap_filename_prefix"
