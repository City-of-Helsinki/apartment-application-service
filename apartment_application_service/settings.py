import environ
import os
import sentry_sdk
import subprocess
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from sentry_sdk.integrations.django import DjangoIntegration

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
    DEFAULT_FROM_EMAIL=(str, ""),
    MAIL_MAILGUN_KEY=(str, ""),
    MAIL_MAILGUN_DOMAIN=(str, ""),
    MAIL_MAILGUN_API=(str, ""),
    MAILER_LOCK_PATH=(str, ""),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, ""),
    LOG_LEVEL=(str, "ERROR"),
    DJANGO_LOG_LEVEL=(str, "ERROR"),
    APPS_LOG_LEVEL=(str, "INFO"),
    CORS_ORIGIN_WHITELIST=(list, []),
    CORS_ORIGIN_ALLOW_ALL=(bool, False),
    OIDC_AUDIENCE=(str, ""),
    OIDC_API_SCOPE_PREFIX=(str, ""),
    OIDC_REQUIRE_API_SCOPE_FOR_AUTHENTICATION=(bool, False),
    OIDC_ISSUER=(str, ""),
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
    APARTMENT_DATA_TRANSFER_PATH=(str, "transfer_files"),
    HASHIDS_SALT=(str, ""),
    PUBLIC_PGP_KEY=(str, ""),
    PRIVATE_PGP_KEY=(str, ""),
)
if os.path.exists(env_file):
    env.read_env(env_file)

BASE_DIR = str(checkout_dir)

DEBUG = env.bool("DEBUG")
SECRET_KEY = env.str("SECRET_KEY")
if DEBUG and not SECRET_KEY:
    SECRET_KEY = "xxx"

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST")

DATABASES = {"default": env.db()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {"default": env.cache()}

EMAIL_CONFIG = env.email_url("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
MAILER_EMAIL_BACKEND = EMAIL_CONFIG["EMAIL_BACKEND"]
MAILER_LOCK_PATH = env.str("MAILER_LOCK_PATH")
EMAIL_BACKEND = "mailer.backend.DbBackend"
if env.str("DEFAULT_FROM_EMAIL"):
    DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL")

try:
    version = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip()
except Exception:
    version = "n/a"

sentry_sdk.init(
    dsn=env.str("SENTRY_DSN"),
    release=version,
    environment=env("SENTRY_ENVIRONMENT"),
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
    "connections",
    "customer",
    "users",
    "audit_log",
    "invoicing",
    "utils",
]

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
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "helusers.oidc.ApiTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
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
}

SOCIAL_AUTH_TUNNISTAMO_KEY = env("SOCIAL_AUTH_TUNNISTAMO_KEY")
SOCIAL_AUTH_TUNNISTAMO_SECRET = env("SOCIAL_AUTH_TUNNISTAMO_SECRET")
SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT = env("SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT")

# Invoicing
INVOICE_NUMBER_PREFIX = "730"

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

HASHIDS_SALT = env("HASHIDS_SALT")
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=30)}

# For pgcrypto
PUBLIC_PGP_KEY = env.str("PUBLIC_PGP_KEY", multiline=True)
PRIVATE_PGP_KEY = env.str("PRIVATE_PGP_KEY", multiline=True)

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
local_settings_path = os.path.join(checkout_dir(), "local_settings.py")
if os.path.exists(local_settings_path):
    with open(local_settings_path) as fp:
        code = compile(fp.read(), local_settings_path, "exec")
    exec(code, globals(), locals())
