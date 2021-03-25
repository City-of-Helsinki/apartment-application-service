import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from rest_framework.test import APIClient

from application_form.tests.factories import UserFactory


@pytest.fixture
def api_client():
    user = UserFactory()
    permissions = Permission.objects.all()
    user.user_permissions.set(permissions)
    client = APIClient()
    client.force_authenticate(user)
    return client


fixtures = ["identifier_schema"]


@pytest.fixture(autouse=True)
def django_fixtures_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command(
            "loaddata", *["{}{}".format(fixture, ".yaml") for fixture in fixtures]
        )
