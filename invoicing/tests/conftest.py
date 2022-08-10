import pytest

from users.tests.conftest import (  # noqa: F401
    api_client,
    sales_ui_salesperson_api_client,
    user_api_client,
)


@pytest.fixture(autouse=True)
def settings_for_tests(settings):
    settings.SAP_SFTP_USERNAME = "test_sap_username"
    settings.SAP_SFTP_PASSWORD = "test_sap_password"
    settings.SAP_SFTP_HOST = "localhost"
    settings.SAP_SFTP_PORT = 22
    settings.SAP_SFTP_FILENAME_PREFIX = "test_sap_filename_prefix"
