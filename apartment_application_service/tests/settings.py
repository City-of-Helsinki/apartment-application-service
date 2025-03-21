import os

import environ

test_env = environ.Env(
    TEST_APARTMENT_INDEX_NAME=(str, "test-apartment"),
    TEST_ELASTICSEARCH_URL=(str, "http://127.0.0.1"),
    TEST_ELASTICSEARCH_PORT=(int, 9200),
    TEST_ELASTICSEARCH_USERNAME=(str, ""),
    TEST_ELASTICSEARCH_PASSWORD=(str, ""),
    TEST_LOG_LEVEL=(str, "INFO"),
)

# Set LOG_LEVEL environment variable before importing real settings
os.environ.setdefault("LOG_LEVEL", test_env("TEST_LOG_LEVEL"))

from ..settings import *  # noqa: E402, F401, F403

IS_TEST = True

TEST_APARTMENT_INDEX_NAME = test_env("TEST_APARTMENT_INDEX_NAME")
APARTMENT_INDEX_NAME = TEST_APARTMENT_INDEX_NAME
APARTMENT_DATA_TRANSFER_PATH = test_env("APARTMENT_DATA_TRANSFER_PATH")
OIKOTIE_SCHEMA_DIR = test_env("OIKOTIE_SCHEMA_DIR")

OIKOTIE_APARTMENTS_BATCH_SCHEMA_URL = test_env(
    "OIKOTIE_APARTMENTS_BATCH_SCHEMA_URL"
)  # noqa: E501
OIKOTIE_APARTMENTS_UPDATE_SCHEMA_URL = test_env(
    "OIKOTIE_APARTMENTS_UPDATE_SCHEMA_URL"
)  # noqa: E501
OIKOTIE_HOUSINGCOMPANIES_BATCH_SCHEMA_URL = test_env(
    "OIKOTIE_HOUSINGCOMPANIES_BATCH_SCHEMA_URL"
)  # noqa: E501

ELASTICSEARCH_URL = test_env("TEST_ELASTICSEARCH_URL")
ELASTICSEARCH_PORT = test_env("TEST_ELASTICSEARCH_PORT")
ELASTICSEARCH_USERNAME = test_env("TEST_ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = test_env("TEST_ELASTICSEARCH_PASSWORD")
