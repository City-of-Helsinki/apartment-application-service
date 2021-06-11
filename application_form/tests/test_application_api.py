import pytest
from django.urls import reverse

from application_form.tests.utils import create_application_data
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_application_post(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201
    assert response.data == {"application_uuid": data["application_uuid"]}


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_application_post_fails_if_not_authenticated(api_client):
    data = create_application_data(ProfileFactory())
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 401
