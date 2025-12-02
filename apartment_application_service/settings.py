import os
from datetime import timedelta

import environ
import sentry_sdk
from django.utils.translation import gettext_lazy as _
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from .utils import is_module_available, scrub_sensitive_payload
from .version import get_version

checkout_dir = environ.Path(__file__) - 2
assert os.path.exists(checkout_dir("manage.py"))

parent_dir = checkout_dir.path("..")
if os.path.isdir(parent_dir("etc")):
    env_file = parent_dir("etc/env")
    default_var_root = parent_dir("var")
else:
    env_file = checkout_dir(".env")
    default_var_root = checkout_dir("var")

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    VAR_ROOT=(str, default_var_root),
    MEDIA_URL=(str, "/media/"),
    STATIC_URL=(str, "/static/"),
    ALLOWED_HOSTS=(list, []),
    USE_X_FORWARDED_HOST=(bool, False),
    DATABASE_URL=(
        str,
        "postgres://apartment-application:apartment-application"
        "@localhost/apartment-application",
    ),
    CACHE_URL=(str, "locmemcache://"),
    DEFAULT_FROM_EMAIL=(str, "asuntomyynti@hel.fi"),
    MAIL_MAILGUN_KEY=(str, ""),
    MAIL_MAILGUN_DOMAIN=(str, ""),
    MAIL_MAILGUN_API=(str, ""),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, ""),
    LOG_LEVEL=(str, "ERROR"),
    DJANGO_LOG_LEVEL=(str, "ERROR"),
    APPS_LOG_LEVEL=(str, "INFO"),
    CORS_ORIGIN_WHITELIST=(list, []),
    CORS_ORIGIN_ALLOW_ALL=(bool, False),
    OIDC_AUDIENCE=(list, []),
    OIDC_API_SCOPE_PREFIX=(list, []),
    OIDC_REQUIRE_API_SCOPE_FOR_AUTHENTICATION=(bool, False),
    OIDC_ISSUER=(list, []),
    OIDC_API_AUTHORIZATION_FIELD=(list, []),
    HELUSERS_BACK_CHANNEL_LOGOUT_ENABLED=(bool, False),
    HELUSERS_USER_MIGRATE_ENABLED=(bool, False),
    SOCIAL_AUTH_TUNNISTAMO_KEY=(str, ""),
    SOCIAL_AUTH_TUNNISTAMO_SECRET=(str, ""),
    SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT=(str, ""),
    ELASTICSEARCH_URL=(str, "http://apartment-application-elasticsearch"),
    ELASTICSEARCH_PORT=(int, 9200),
    ELASTICSEARCH_USERNAME=(str, ""),
    ELASTICSEARCH_PASSWORD=(str, ""),
    APARTMENT_INDEX_NAME=(str, "asuntotuotanto-apartments"),
    ETUOVI_SUPPLIER_SOURCE_ITEMCODE=(str, ""),
    ETUOVI_COMPANY_NAME=(str, ""),
    ETUOVI_TRANSFER_ID=(str, ""),
    ETUOVI_FTP_HOST=(str, ""),
    ETUOVI_USER=(str, ""),
    ETUOVI_PASSWORD=(str, ""),
    OIKOTIE_VENDOR_ID=(str, ""),
    OIKOTIE_COMPANY_NAME=(str, ""),
    OIKOTIE_ENTRYPOINT=(str, ""),
    OIKOTIE_TRANSFER_ID=(str, ""),
    OIKOTIE_FTP_HOST=(str, ""),
    OIKOTIE_USER=(str, ""),
    OIKOTIE_PASSWORD=(str, ""),
    OIKOTIE_SCHEMA_DIR=(str, ""),
    OIKOTIE_APARTMENTS_BATCH_SCHEMA_URL=(str, ""),
    OIKOTIE_APARTMENTS_UPDATE_SCHEMA_URL=(str, ""),
    OIKOTIE_HOUSINGCOMPANIES_BATCH_SCHEMA_URL=(str, ""),
    APARTMENT_DATA_TRANSFER_PATH=(str, "transfer_files"),
    HASHIDS_SALT=(str, ""),
    PUBLIC_PGP_KEY=(str, ""),
    PRIVATE_PGP_KEY=(str, ""),
    SAP_SFTP_USERNAME=(str, ""),
    SAP_SFTP_PASSWORD=(str, ""),
    SAP_SFTP_HOST=(str, ""),
    SAP_SFTP_PORT=(int, 22),
    SAP_SFTP_FILENAME_PREFIX=(str, "MR_IN_ID066_2800_"),
    SAP_SFTP_SEND_USERNAME=(str, ""),
    SAP_SFTP_SEND_PASSWORD=(str, ""),
    SAP_SFTP_SEND_HOST=(str, ""),
    SAP_SFTP_SEND_PORT=(int, 22),
    SAP_SFTP_SEND_FILENAME_PREFIX=(str, "MR_IN_ID066_2800_"),
    SAP_DAYS_UNTIL_INSTALLMENT_DUE_DATE=(int, 30),
    SAP_SFTP_FETCH_USERNAME=(str, ""),
    SAP_SFTP_FETCH_PASSWORD=(str, ""),
    SAP_SFTP_FETCH_HOST=(str, ""),
    SAP_SFTP_FETCH_PORT=(int, 22),
    METADATA_HANDLER_INFORMATION=(
        str,
        "0201256-6 / Kaupunkiympäristön toimiala / Asuntotuotanto / Asuntomyynti",
    ),
    METADATA_HITAS_PROCESS_NUMBER=(str, "10 07 05 00"),
    METADATA_HASO_PROCESS_NUMBER=(str, "10 07 04 01"),
    TALPA_EMAIL=(str, ""),
    TALPA_EMAIL_REPLY_TO=(str, "asuntomyynti@hel.fi"),
    ELASTICSEARCH_APP_AUDIT_LOG_INDEX=(str, "apartment_application_audit_log"),
    AUDIT_LOG_ELASTICSEARCH_HOST=(str, ""),
    AUDIT_LOG_ELASTICSEARCH_PORT=(str, ""),
    AUDIT_LOG_ELASTICSEARCH_USERNAME=(str, ""),
    AUDIT_LOG_ELASTICSEARCH_PASSWORD=(str, ""),
    ENABLE_SEND_AUDIT_LOG=(bool, False),
    CLEAR_AUDIT_LOG_ENTRIES=(bool, False),
    DRUPAL_SERVER_AUTH_TOKEN=(str, "example-token"),
    DEFAULT_SOLD_APARMENT_TIME_RANGE=(int, 1),
    DEFAULT_APARTMENT_REVALUATION_TIME_RANGE=(int, 1),
    APPLICANT_DUPLICATE_VALIDATION_DISABLED=(bool, False),
)
if os.path.exists(env_file):
    env.read_env(env_file)

BASE_DIR = str(checkout_dir)

DEBUG = env.bool("DEBUG")
SECRET_KEY = env.str("SECRET_KEY")
if DEBUG and not SECRET_KEY:
    SECRET_KEY = "xxx"

# if running automated tests. Can be overridden by tests
IS_TEST = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST")

DATABASES = {"default": env.db()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {"default": env.cache()}

EMAIL_CONFIG = env.email_url("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)

if env.str("DEFAULT_FROM_EMAIL"):
    DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL")

SENTRY_DSN = env.str("SENTRY_DSN")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT")
if SENTRY_DSN and SENTRY_ENVIRONMENT:
    # scrub ssn_suffix
    custom_denylist = DEFAULT_DENYLIST + ["ssn_suffix"]

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=get_version(),
        environment=SENTRY_ENVIRONMENT,
        before_send=scrub_sensitive_payload,
        event_scrubber=EventScrubber(denylist=custom_denylist),
        integrations=[DjangoIntegration()],
    )

var_root = env.path("VAR_ROOT")
MEDIA_ROOT = var_root("media")
STATIC_ROOT = var_root("static")
MEDIA_URL = env.str("MEDIA_URL")
STATIC_URL = env.str("STATIC_URL")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

ROOT_URLCONF = "apartment_application_service.urls"
WSGI_APPLICATION = "apartment_application_service.wsgi.application"

LANGUAGE_CODE = "fi"
LANGUAGES = (("fi", _("Finnish")), ("en", _("English")), ("sv", _("Swedish")))
TIME_ZONE = "Europe/Helsinki"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

INSTALLED_APPS = [
    "helusers.apps.HelusersConfig",
    "helusers.apps.HelusersAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "social_django",
    "rest_framework",
    "simple_history",
    "drf_spectacular",
    "pgcrypto",
    # local apps
    "apartment",
    "application_form",
    "asko_import",
    "connections",
    "customer",
    "users",
    "audit_log",
    "invoicing",
    "utils",
    "cost_index",
]

if DEBUG and is_module_available("django_extensions"):
    INSTALLED_APPS += ["django_extensions"]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

AUTH_USER_MODEL = "users.User"

CORS_ORIGIN_WHITELIST = env.list("CORS_ORIGIN_WHITELIST")
CORS_ORIGIN_ALLOW_ALL = env.bool("CORS_ORIGIN_ALLOW_ALL")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s p%(process)d %(name)s %(levelname)s: %(message)s"
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "loggers": {
        "": {"level": env("LOG_LEVEL"), "handlers": ["console"]},
        "django": {
            "level": env("DJANGO_LOG_LEVEL"),
            "handlers": ["console"],
            "propagate": False,
        },
        "connections": {
            "level": env("APPS_LOG_LEVEL"),
            "handlers": ["console"],
            # required to avoid double logging with root logger
            "propagate": False,
        },
        "users": {
            "level": env("APPS_LOG_LEVEL"),
            "handlers": ["console"],
            # required to avoid double logging with root logger
            "propagate": False,
        },
        "invoicing": {
            "level": env("APPS_LOG_LEVEL"),
            "handlers": ["console"],
            # required to avoid double logging with root logger
            "propagate": False,
        },
        "asko_import": {"level": env("APPS_LOG_LEVEL")},
    },
}

SITE_ID = 1

# Authentication

AUTHENTICATION_BACKENDS = (
    "helusers.tunnistamo_oidc.TunnistamoOIDCAuth",
    "django.contrib.auth.backends.ModelBackend",
)

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apartment_application_service.oidc.TunnistamoFixedApiTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("users.permissions.IsDjangoSalesperson",),
    "DEFAULT_SCHEMA_CLASS": "apartment_application_service.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apartment_application_service.exceptions.drf_exception_handler",  # noqa: E501
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Apartment Application API",
    "DESCRIPTION": "Apartment application service for the City of Helsinki.",
    "VERSION": None,
    "SCHEMA_PATH_PREFIX": r"/v[0-9]+",
    "SERVE_INCLUDE_SCHEMA": False,
}

OIDC_API_TOKEN_AUTH = {
    "AUDIENCE": env("OIDC_AUDIENCE"),
    "API_SCOPE_PREFIX": env("OIDC_API_SCOPE_PREFIX"),
    "REQUIRE_API_SCOPE_FOR_AUTHENTICATION": env(
        "OIDC_REQUIRE_API_SCOPE_FOR_AUTHENTICATION"
    ),
    "ISSUER": env("OIDC_ISSUER"),
    "API_AUTHORIZATION_FIELD": env("OIDC_API_AUTHORIZATION_FIELD"),
}

HELUSERS_BACK_CHANNEL_LOGOUT_ENABLED = env("HELUSERS_BACK_CHANNEL_LOGOUT_ENABLED")
HELUSERS_USER_MIGRATE_ENABLED = env("HELUSERS_USER_MIGRATE_ENABLED")

# drf-oidc-auth rejects tokens older this so we don't want to use the default value 600s
# see https://github.com/ByteInternet/drf-oidc-auth/issues/28
OIDC_AUTH = {"OIDC_LEEWAY": 61 * 60}

SOCIAL_AUTH_TUNNISTAMO_KEY = env("SOCIAL_AUTH_TUNNISTAMO_KEY")
SOCIAL_AUTH_TUNNISTAMO_SECRET = env("SOCIAL_AUTH_TUNNISTAMO_SECRET")
SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT = env("SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT")

# Invoicing
INVOICE_NUMBER_PREFIX = "730"

# SAP
SAP = {
    "SENDER_ID": "ID066",
    "COMPANY_CODE": "2800",
    "DOCUMENT_TYPE": "5R",
    "CURRENCY_CODE": "EUR",
    "TAX_CODE": "4Z",
    "PAYMENT_TERMS": "N073",
    "GL_ACCOUNT": "350080",
    "WBS_ELEMENT": {
        "PREFIX": "282500",
        "OWNERSHIP_TYPE_CODE": {
            "HASO": "2",
            "HITAS": "4",
            "PUOLIHITAS": "6",
        },
        "REVENUE_TYPE_CODE": {
            "HASO": "02303",
            "HITAS": "02302",
            "PUOLIHITAS": "02302",
        },
    },
}

# Common SAP SFTP settings for both Send and Fetch.
#
# These will be used as defaults for both sending and fetching
SAP_SFTP_USERNAME = env("SAP_SFTP_USERNAME")
SAP_SFTP_PASSWORD = env("SAP_SFTP_PASSWORD")
SAP_SFTP_HOST = env("SAP_SFTP_HOST")
SAP_SFTP_PORT = env("SAP_SFTP_PORT")
SAP_SFTP_FILENAME_PREFIX = env("SAP_SFTP_FILENAME_PREFIX")

# SAP SFTP settings for sending (invoices/installments)
SAP_SFTP_SEND_USERNAME = env("SAP_SFTP_SEND_USERNAME", default=SAP_SFTP_USERNAME)
SAP_SFTP_SEND_PASSWORD = env("SAP_SFTP_SEND_PASSWORD", default=SAP_SFTP_PASSWORD)
SAP_SFTP_SEND_HOST = env("SAP_SFTP_SEND_HOST", default=SAP_SFTP_HOST)
SAP_SFTP_SEND_PORT = env("SAP_SFTP_SEND_PORT", default=SAP_SFTP_PORT)
SAP_SFTP_SEND_FILENAME_PREFIX = env(
    "SAP_SFTP_SEND_FILENAME_PREFIX", default=SAP_SFTP_FILENAME_PREFIX
)

# Installments won't be sent to SAP before their due date is at least this close
# (in days)
SAP_DAYS_UNTIL_INSTALLMENT_DUE_DATE = env("SAP_DAYS_UNTIL_INSTALLMENT_DUE_DATE")

# SAP SFTP settings for fetching (payment statuses)
SAP_SFTP_FETCH_USERNAME = env("SAP_SFTP_FETCH_USERNAME", default=SAP_SFTP_USERNAME)
SAP_SFTP_FETCH_PASSWORD = env("SAP_SFTP_FETCH_PASSWORD", default=SAP_SFTP_PASSWORD)
SAP_SFTP_FETCH_HOST = env("SAP_SFTP_FETCH_HOST", default=SAP_SFTP_HOST)
SAP_SFTP_FETCH_PORT = env("SAP_SFTP_FETCH_PORT", default=SAP_SFTP_PORT)

# Elasticsearch
ELASTICSEARCH_URL = env("ELASTICSEARCH_URL")
ELASTICSEARCH_PORT = env("ELASTICSEARCH_PORT")
ELASTICSEARCH_USERNAME = env("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = env("ELASTICSEARCH_PASSWORD")
APARTMENT_INDEX_NAME = env("APARTMENT_INDEX_NAME")

# Etuovi settings
ETUOVI_SUPPLIER_SOURCE_ITEMCODE = env("ETUOVI_SUPPLIER_SOURCE_ITEMCODE")
ETUOVI_COMPANY_NAME = env("ETUOVI_COMPANY_NAME")
ETUOVI_TRANSFER_ID = env("ETUOVI_TRANSFER_ID")
ETUOVI_FTP_HOST = env("ETUOVI_FTP_HOST")
ETUOVI_USER = env("ETUOVI_USER")
ETUOVI_PASSWORD = env("ETUOVI_PASSWORD")

# Oikotie settings
OIKOTIE_VENDOR_ID = env("OIKOTIE_VENDOR_ID")
OIKOTIE_COMPANY_NAME = env("OIKOTIE_COMPANY_NAME")
OIKOTIE_ENTRYPOINT = env("OIKOTIE_ENTRYPOINT")
OIKOTIE_TRANSFER_ID = env("OIKOTIE_TRANSFER_ID")
OIKOTIE_FTP_HOST = env("OIKOTIE_FTP_HOST")
OIKOTIE_USER = env("OIKOTIE_USER")
OIKOTIE_PASSWORD = env("OIKOTIE_PASSWORD")
APARTMENT_DATA_TRANSFER_PATH = env("APARTMENT_DATA_TRANSFER_PATH")
OIKOTIE_SCHEMA_DIR = env("OIKOTIE_SCHEMA_DIR")

OIKOTIE_APARTMENTS_BATCH_SCHEMA = env("OIKOTIE_APARTMENTS_BATCH_SCHEMA_URL").split("/")[
    -1
]  # noqa: E501
OIKOTIE_APARTMENTS_UPDATE_SCHEMA = env("OIKOTIE_APARTMENTS_UPDATE_SCHEMA_URL").split(
    "/"
)[
    -1
]  # noqa: E501
OIKOTIE_HOUSINGCOMPANIES_BATCH_SCHEMA = env(
    "OIKOTIE_HOUSINGCOMPANIES_BATCH_SCHEMA_URL"
).split("/")[
    -1
]  # noqa: E501

HASHIDS_SALT = env("HASHIDS_SALT")
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=30)}

# For pgcrypto
PUBLIC_PGP_KEY = env.str("PUBLIC_PGP_KEY", multiline=True)
PRIVATE_PGP_KEY = env.str("PRIVATE_PGP_KEY", multiline=True)

# Metadata constants =
METADATA_HANDLER_INFORMATION = env.str("METADATA_HANDLER_INFORMATION")
METADATA_HITAS_PROCESS_NUMBER = env.str("METADATA_HITAS_PROCESS_NUMBER")
METADATA_HASO_PROCESS_NUMBER = env.str("METADATA_HASO_PROCESS_NUMBER")

TALPA_EMAIL = env.str("TALPA_EMAIL")
TALPA_EMAIL_REPLY_TO = env.str("TALPA_EMAIL_REPLY_TO")

# Audit logging
CLEAR_AUDIT_LOG_ENTRIES = env.bool("CLEAR_AUDIT_LOG_ENTRIES")
ELASTICSEARCH_APP_AUDIT_LOG_INDEX = env("ELASTICSEARCH_APP_AUDIT_LOG_INDEX")
AUDIT_LOG_ELASTICSEARCH_HOST = env("AUDIT_LOG_ELASTICSEARCH_HOST")
AUDIT_LOG_ELASTICSEARCH_PORT = env("AUDIT_LOG_ELASTICSEARCH_PORT")
AUDIT_LOG_ELASTICSEARCH_USERNAME = env("AUDIT_LOG_ELASTICSEARCH_USERNAME")
AUDIT_LOG_ELASTICSEARCH_PASSWORD = env("AUDIT_LOG_ELASTICSEARCH_PASSWORD")
ENABLE_SEND_AUDIT_LOG = env("ENABLE_SEND_AUDIT_LOG")

# Drupal auth
DRUPAL_SERVER_AUTH_TOKEN = env.str("DRUPAL_SERVER_AUTH_TOKEN")
DEFAULT_SOLD_APARMENT_TIME_RANGE = env.int("DEFAULT_SOLD_APARMENT_TIME_RANGE")  # hours
DEFAULT_APARTMENT_REVALUATION_TIME_RANGE = env.int(
    "DEFAULT_APARTMENT_REVALUATION_TIME_RANGE"
)  # hours

# Tunables
APPLICANT_DUPLICATE_VALIDATION_DISABLED = env.bool(
    "APPLICANT_DUPLICATE_VALIDATION_DISABLED"
)

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
local_settings_path = os.path.join(checkout_dir(), "local_settings.py")
if os.path.exists(local_settings_path):
    with open(local_settings_path) as fp:
        code = compile(fp.read(), local_settings_path, "exec")
    exec(code, globals(), locals())
