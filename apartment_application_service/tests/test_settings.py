"""
Test cases for Django 5.2 compatible project settings.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from importlib import import_module

import pytest
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

import apartment_application_service.settings as project_settings
from users.enums import Roles
from users.tests.factories import UserFactory

TYPICAL_SESSION_VALUES = {
    "string_value": "value",
    "int_value": 42,
    "bool_value": True,
    "none_value": None,
    "list_value": ["a", 1, None],
    "dict_value": {"nested": {"key": "value"}, "items": [1, 2]},
    "social_auth_last_login_backend": "tunnistamo",
    "next": "/admin/",
}


def _session_store_class():
    """
    Return the SessionStore class of the configured session engine.

            Returns:
                    session_store_class (type): SessionStore of SESSION_ENGINE
    """
    return import_module(settings.SESSION_ENGINE).SessionStore


def _logged_in_salesperson_client():
    """
    Return an API client logged in through a real session as a salesperson.

            Returns:
                    client (APIClient): Client with a session cookie set
    """
    user = UserFactory()
    Group.objects.get(name__iexact=Roles.DJANGO_SALESPERSON.name).user_set.add(user)
    client = APIClient()
    client.force_login(user)
    client.user = user
    return client


@pytest.mark.django_db
def test_session_round_trip_preserves_typical_values():
    """
    - A logged-in session is stored with the configured engine and serializer.
    - Typical str, int, bool, None, list and dict values survive a reload.
    - The auth session keys survive a reload.
    """
    client = _logged_in_salesperson_client()
    session = client.session
    for key, value in TYPICAL_SESSION_VALUES.items():
        session[key] = value
    session.save()

    reloaded = _session_store_class()(session_key=session.session_key)

    for key, value in TYPICAL_SESSION_VALUES.items():
        assert reloaded[key] == value
    assert reloaded[SESSION_KEY] == str(client.user.pk)
    assert reloaded[BACKEND_SESSION_KEY] == session[BACKEND_SESSION_KEY]
    assert reloaded[HASH_SESSION_KEY] == client.user.get_session_auth_hash()


@pytest.mark.django_db
def test_logged_in_session_authenticates_api_request():
    """
    - A session stored with the configured serializer authenticates a request.
    - The session still authenticates after typical values are added to it.
    """
    client = _logged_in_salesperson_client()
    session = client.session
    for key, value in TYPICAL_SESSION_VALUES.items():
        session[key] = value
    session.save()

    response = client.get(reverse("customer:sales-customer-list"), format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.wsgi_request.user == client.user


@pytest.mark.django_db
def test_request_without_session_is_not_authenticated():
    """
    - A request without a logged-in session is rejected.
    """
    response = APIClient().get(reverse("customer:sales-customer-list"), format="json")

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [datetime(2024, 1, 1, tzinfo=dt_timezone.utc), {"a", "b"}, b"bytes"],
    ids=["datetime", "set", "bytes"],
)
def test_session_rejects_non_json_serializable_values(value):
    """
    - Saving a session with a non JSON serializable value raises TypeError.
    - Fails while PickleSerializer (removed in Django 5.0) is configured.
    """
    session = _session_store_class()()
    session["value"] = value

    with pytest.raises(TypeError):
        session.save()


def test_storages_backends_are_configured():
    """
    - Static files use the WhiteNoise compressed manifest storage.
    - Default file storage uses the file system storage.
    """
    assert (
        settings.STORAGES["staticfiles"]["BACKEND"]
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
    assert (
        settings.STORAGES["default"]["BACKEND"]
        == "django.core.files.storage.FileSystemStorage"
    )


@pytest.mark.parametrize(
    "setting_name",
    ["STATICFILES_STORAGE", "DEFAULT_FILE_STORAGE", "USE_L10N"],
)
def test_project_settings_do_not_define_removed_settings(setting_name):
    """
    - STATICFILES_STORAGE and DEFAULT_FILE_STORAGE (removed in Django 5.1)
      are not set in project settings.
    - USE_L10N (removed in Django 5.0) is not set in project settings.
    """
    assert not hasattr(project_settings, setting_name)
