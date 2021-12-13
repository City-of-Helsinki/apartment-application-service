import pytest
import uuid
from django.urls import reverse

from apartment.tests.factories import ApartmentDocumentFactory
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_apartment_list_get(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(reverse("apartment:apartment-list"), format="json")
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_apartment_list_get_with_project_uuid(api_client):
    apartment = ApartmentDocumentFactory(project_uuid=uuid.uuid4())
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": apartment.project_uuid}
    response = api_client.get(
        reverse("apartment:apartment-list"),
        data=data,
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0].get("uuid") == apartment.uuid


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_list_get(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(reverse("apartment:project-list"), format="json")
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_get_with_project_uuid(api_client):
    apartment = ApartmentDocumentFactory(project_uuid=uuid.uuid4())
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": apartment.project_uuid}
    response = api_client.get(
        reverse("apartment:project-list"),
        data=data,
        format="json",
    )
    assert response.status_code == 200
    assert response.data
    assert response.data.get("uuid") == str(apartment.project_uuid)


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_get_with_project_uuid_not_exist(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": uuid.uuid4()}
    response = api_client.get(
        reverse("apartment:project-list"),
        data=data,
        format="json",
    )
    assert response.status_code == 404
