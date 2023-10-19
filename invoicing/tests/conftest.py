import pytest

from users.tests.conftest import (  # noqa: F401
    api_client,
    sales_ui_salesperson_api_client,
    user_api_client,
)


@pytest.fixture(autouse=True)
def settings_for_tests(settings):
    settings.SAP_SFTP_SEND_USERNAME = "test_sap_username"
    settings.SAP_SFTP_SEND_PASSWORD = "test_sap_password"
    settings.SAP_SFTP_SEND_HOST = "localhost"
    settings.SAP_SFTP_SEND_PORT = 22
    settings.SAP_SFTP_SEND_FILENAME_PREFIX = "test_sap_filename_prefix"
