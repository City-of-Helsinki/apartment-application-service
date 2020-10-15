import pytest
from rest_framework.reverse import reverse

from application_form.api.serializers import HasoSerializer
from application_form.tests.factories import HasoApplicationFactory

list_url = reverse("v1:hasoapplication-list")


HASO_APPLICATION_TEST_DATA = {
    "right_of_occupancy_id": "123456789",
    "current_housing": "Asumisoikeusasunto",
    "housing_description": "test",
    "housing_type": "test, 5h+k",
    "housing_area": 35.5,
    "is_changing_occupancy_apartment": True,
    "is_over_55": True,
    "project_uuid": "aabf22f3-5d09-47dc-bd89-ab744b905a17",
    "apartment_uuids": [
        "55796dd1-bd35-42c4-82bb-6a7e9898d0ff",
        "11993697-a0c1-4c07-b38e-b293c3875137",
    ],
}


@pytest.mark.django_db
def test_haso_application_create(api_client):
    response = api_client.post(list_url, HASO_APPLICATION_TEST_DATA)

    assert response.status_code == 201


@pytest.mark.django_db
def test_haso_applications_read(api_client):
    HasoApplicationFactory()
    response = api_client.get(list_url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_haso_application_single_read(api_client):
    haso_application = HasoApplicationFactory()
    response = api_client.get(
        reverse("v1:hasoapplication-detail", kwargs={"pk": haso_application.id})
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_haso_application_udpdate(api_client):
    haso_application = HasoApplicationFactory()
    serializer = HasoSerializer(haso_application)
    data = serializer.data
    data["is_changing_occupancy_apartment"] = False
    response = api_client.put(
        reverse("v1:hasoapplication-detail", kwargs={"pk": haso_application.id}), data
    )

    assert response.status_code == 200
    assert response.data["is_changing_occupancy_apartment"] is False


@pytest.mark.django_db
def test_haso_application_delete(api_client):
    haso_application = HasoApplicationFactory()
    response = api_client.delete(
        reverse("v1:hasoapplication-detail", kwargs={"pk": haso_application.id})
    )

    assert response.status_code == 204
