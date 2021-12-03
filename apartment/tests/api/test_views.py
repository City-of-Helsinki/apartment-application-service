import pytest
from django.urls import reverse

from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_list_get(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(reverse("apartment:project-list"), format="json")
    assert response.status_code == 200
    assert len(response.data) > 0
