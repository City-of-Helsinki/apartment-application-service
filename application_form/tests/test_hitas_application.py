import pytest
from rest_framework.reverse import reverse

from application_form.api.serializers import HitasSerializer
from application_form.tests.factories import HitasApplicationFactory

list_url = reverse("v1/applications:hitasapplication-list")


HITAS_APPLICATION_TEST_DATA = {
    "has_previous_hitas_apartment": True,
    "previous_hitas_description": "WqQAZURKDxBk",
    "has_children": True,
    "apartment_uuid": "e6dd9eff-6bfa-49c6-98ae-24290d220ef2",
    "applicant_token": "8fc6b646-bce8-4143-a33c-be91975080c4",
}


@pytest.mark.django_db
def test_hitas_application_create(api_client):
    response = api_client.post(list_url, HITAS_APPLICATION_TEST_DATA)

    assert response.status_code == 201
    assert HITAS_APPLICATION_TEST_DATA["apartment_uuid"] == str(
        response.data["apartment_uuid"]
    )


@pytest.mark.django_db
def test_hitas_applications_read(api_client):
    hitas_application = HitasApplicationFactory()
    response = api_client.get(list_url)

    assert response.status_code == 200
    assert str(hitas_application.apartment.apartment_uuid) == str(
        response.data[0]["apartment_uuid"]
    )


@pytest.mark.django_db
def test_hitas_application_single_read(api_client):
    hitas_application = HitasApplicationFactory()
    response = api_client.get(
        reverse(
            "v1/applications:hitasapplication-detail",
            kwargs={"pk": hitas_application.id},
        )
    )

    assert response.status_code == 200
    assert str(hitas_application.apartment.apartment_uuid) == str(
        response.data["apartment_uuid"]
    )


@pytest.mark.django_db
def test_hitas_application_update(api_client):
    hitas_application = HitasApplicationFactory()
    serializer = HitasSerializer(hitas_application)
    data = serializer.data
    data["has_children"] = False
    response = api_client.put(
        reverse(
            "v1/applications:hitasapplication-detail",
            kwargs={"pk": hitas_application.id},
        ),
        data,
    )

    assert response.status_code == 200
    assert response.data["has_children"] is False
    assert str(hitas_application.apartment.apartment_uuid) == str(
        response.data["apartment_uuid"]
    )


@pytest.mark.django_db
def test_hitas_application_delete(api_client):
    hitas_application = HitasApplicationFactory()
    response = api_client.delete(
        reverse(
            "v1/applications:hitasapplication-detail",
            kwargs={"pk": hitas_application.id},
        )
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_application_approve_leaves_a_history_changelog():
    application = HitasApplicationFactory()
    application.approve()
    assert application.history.first().history_change_reason == "application approved."


@pytest.mark.django_db
def test_application_reject_leaves_a_history_changelog():
    application = HitasApplicationFactory()
    application.reject("rejected")
    assert application.history.first().history_change_reason == "application rejected."


@pytest.mark.django_db
def test_accept_offer():
    application = HitasApplicationFactory(is_approved=True)
    apartment = application.apartment
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
