import environ
import os
import sentry_sdk
import subprocess
from django.utils.translation import ugettext_lazy as _
from sentry_sdk.integrations.django import DjangoIntegration

checkout_dir = environ.Path(__file__) - 2
assert os.path.exists(checkout_dir("manage.py"))

parent_dir = checkout_dir.path("..")
if os.path.isdir(parent_dir("etc")):
    env_file = parent_dir("etc/env")
    default_var_root = environ.Path(parent_dir("var"))
else:
    env_file = checkout_dir(".env")
    default_var_root = environ.Path(checkout_dir("var"))

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    MEDIA_ROOT=(environ.Path(), default_var_root("media")),
    STATIC_ROOT=(environ.Path(), default_var_root("static")),
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
    EMAIL_URL=(str, "consolemail://"),
    DEFAULT_FROM_EMAIL=(str, ""),
    MAIL_MAILGUN_KEY=(str, ""),
    MAIL_MAILGUN_DOMAIN=(str, ""),
    MAIL_MAILGUN_API=(str, ""),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, ""),
    LOG_LEVEL=(str, ""),
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
    APARTMENT_INDEX_NAME=(str, ""),
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

CACHES = {"default": env.cache()}
vars().update(env.email_url())  # EMAIL_BACKEND etc.
MAILER_EMAIL_BACKEND = EMAIL_BACKEND  # noqa: F821
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

MEDIA_ROOT = env("MEDIA_ROOT")
STATIC_ROOT = env("STATIC_ROOT")
MEDIA_URL = env.str("MEDIA_URL")
STATIC_URL = env.str("STATIC_URL")

ROOT_URLCONF = "apartment_application_service.urls"
WSGI_APPLICATION = "apartment_application_service.wsgi.application"

LANGUAGE_CODE = "fi"
LANGUAGES = (("fi", _("Finnish")), ("en", _("English")), ("sv", _("Swedish")))
TIME_ZONE = "Europe/Helsinki"
USE_I18N = True
USE_L10N = True
USE_TZ = True

INSTALLED_APPS = [
    "helusers.apps.HelusersConfig",
    "helusers.apps.HelusersAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "parler",
    "anymail",
    "mailer",
    "django_ilmoitin",
    "social_django",
    "rest_framework",
    "simple_history",
    # local apps
    "application_form",
    "connections",
    "users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "standard": {
            "format": "%(asctime)s p%(process)d %(name)s %(levelname)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S.%03dZ",
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "loggers": {
        "": {
            "level": "WARNING",
            "handlers": [
                "console",
            ],
        },
        "connections": {
            "level": env("LOG_LEVEL"),
            "handlers": [
                "console",
            ],
            # required to avoid double logging with root logger
            "propagate": False,
        },
    },
}

SITE_ID = 1

PARLER_LANGUAGES = {SITE_ID: ({"code": "fi"}, {"code": "en"}, {"code": "sv"})}

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
        "helusers.oidc.ApiTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
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

# Elasticsearch
ELASTICSEARCH_URL = env("ELASTICSEARCH_URL")
ELASTICSEARCH_PORT = env("ELASTICSEARCH_PORT")
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

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
local_settings_path = os.path.join(checkout_dir(), "local_settings.py")
if os.path.exists(local_settings_path):
    with open(local_settings_path) as fp:
        code = compile(fp.read(), local_settings_path, "exec")
    exec(code, globals(), locals())
