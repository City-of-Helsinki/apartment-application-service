import pytest
from rest_framework.reverse import reverse

from application_form.api.serializers import HasoSerializer
from application_form.tests.factories import HasoApplicationFactory

list_url = reverse("v1/applications:hasoapplication-list")


HASO_APPLICATION_TEST_DATA = {
    "right_of_occupancy_id": "123456789",
    "current_housing": "Asumisoikeusasunto",
    "housing_description": "test",
    "housing_type": "test, 5h+k",
    "housing_area": 35.5,
    "is_changing_occupancy_apartment": True,
    "is_over_55": True,
    "applicant_token": "8fc6b646-bce8-4143-a33c-be91975080c4",
    "apartment_uuids": [
        "55796dd1-bd35-42c4-82bb-6a7e9898d0ff",
        "11993697-a0c1-4c07-b38e-b293c3875137",
        "53123618-8a4d-4d6a-90d1-748cd64bbcd1",
        "ded49be3-b307-4148-ac2e-56893e0d943c",
        "cb0de199-356a-4faa-a883-745938d9bc44",
    ],
}


@pytest.mark.django_db
def test_haso_application_create(api_client):
    response = api_client.post(list_url, HASO_APPLICATION_TEST_DATA)

    assert response.status_code == 201
    for idx, apartment_uuid in enumerate(HASO_APPLICATION_TEST_DATA["apartment_uuids"]):
        assert str(apartment_uuid) == str(response.data["apartment_uuids"][idx])


@pytest.mark.django_db
def test_haso_applications_read(api_client):
    haso_application = HasoApplicationFactory()
    response = api_client.get(list_url)

    assert response.status_code == 200
    for idx, apartment_uuid in enumerate(
        haso_application.haso_apartment_priorities.order_by(
            "priority_number"
        ).values_list("apartment", flat=True)
    ):
        assert str(apartment_uuid) == str(response.data[0]["apartment_uuids"][idx])


@pytest.mark.django_db
def test_haso_application_single_read(api_client):
    haso_application = HasoApplicationFactory()
    response = api_client.get(
        reverse(
            "v1/applications:hasoapplication-detail", kwargs={"pk": haso_application.id}
        )
    )

    assert response.status_code == 200
    for idx, apartment_uuid in enumerate(
        haso_application.haso_apartment_priorities.order_by(
            "priority_number"
        ).values_list("apartment", flat=True)
    ):
        assert str(apartment_uuid) == str(response.data["apartment_uuids"][idx])


@pytest.mark.django_db
def test_haso_application_update(api_client):
    haso_application = HasoApplicationFactory()
    serializer = HasoSerializer(haso_application)
    data = serializer.data
    data["is_changing_occupancy_apartment"] = False
    response = api_client.put(
        reverse(
            "v1/applications:hasoapplication-detail", kwargs={"pk": haso_application.id}
        ),
        data,
    )

    assert response.status_code == 200
    assert response.data["is_changing_occupancy_apartment"] is False
    for idx, apartment_uuid in enumerate(
        haso_application.haso_apartment_priorities.order_by(
            "priority_number"
        ).values_list("apartment", flat=True)
    ):
        assert str(apartment_uuid) == (response.data["apartment_uuids"][idx])


@pytest.mark.django_db
def test_haso_application_delete(api_client):
    haso_application = HasoApplicationFactory()
    response = api_client.delete(
        reverse(
            "v1/applications:hasoapplication-detail", kwargs={"pk": haso_application.id}
        )
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_application_approve_leaves_a_history_changelog():
    application = HasoApplicationFactory()
    application.approve()
    assert application.history.first().history_change_reason == "application approved."


@pytest.mark.django_db
def test_application_reject_leaves_a_history_changelog():
    application = HasoApplicationFactory()
    application.reject("rejected")
    assert application.history.first().history_change_reason == "application rejected."


@pytest.mark.django_db
def test_accept_offer():
    application = HasoApplicationFactory(is_approved=True)
    apartment = application.haso_apartment_priorities.first().apartment
    application.accept_offer(apartment)

    assert application.applicant_has_accepted_offer is True
    assert apartment.is_available is False
    assert (
        application.history.first().history_change_reason
        == "applicant has accepted an offer."
    )
    assert (
        apartment.history.first().history_change_reason
        == "apartment offer accepted by an applicant."
    )
    assert application.haso_apartment_priorities.filter(is_active=True).count() == 1
    for haso_apartment_priority in application.haso_apartment_priorities.filter(
        is_active=False
    ):
        assert (
            haso_apartment_priority.history.first().history_change_reason
            == "haso application deactivated due to accepted offer."
        )
