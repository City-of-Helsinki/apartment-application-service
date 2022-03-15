import pytest
import uuid
from django.urls import reverse

from application_form.tests.factories import (
    ApartmentReservationFactory,
    LotteryEventFactory,
)
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
def test_apartment_list_get_with_project_uuid(
    api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = {"project_uuid": project_uuid}
    response = api_client.get(
        reverse("apartment:apartment-list"),
        data=data,
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == 5
    assert response.data[0].get("uuid") == apartments[0].uuid


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_list_get(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(reverse("apartment:project-list"), format="json")
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["list", "detail"])
@pytest.mark.parametrize("lottery_exists", (True, False))
def test_project_list_lottery_completed_field(
    api_client, elastic_project_with_5_apartments, endpoint, lottery_exists
):
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    if lottery_exists:
        LotteryEventFactory(apartment_uuid=apartments[0].uuid)

    url = (
        reverse("apartment:project-list")
        if endpoint == "list"
        else reverse(
            "apartment:project-detail",
            kwargs={"project_uuid": project_uuid},
        )
    )
    response = api_client.get(url, format="json")
    assert response.status_code == 200

    data = response.data[0] if endpoint == "list" else response.data
    assert data["lottery_completed"] is lottery_exists


@pytest.mark.django_db
def test_project_get_with_project_uuid(api_client, elastic_project_with_5_apartments):
    project_uuid, _ = elastic_project_with_5_apartments
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200
    assert response.data
    assert response.data.get("uuid") == str(project_uuid)


@pytest.mark.django_db
def test_project_get_with_project_uuid_not_exist(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": uuid.uuid4()}),
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_project_detail_apartment_reservations(
    api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5
    expect_reservations_per_apartment_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        for _ in range(0, expect_reservations_per_apartment_count):
            ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200
    assert response.data

    assert response.data["apartments"]
    apartments_data = response.data["apartments"]
    assert len(apartments_data) == expect_apartments_count

    apartments = {apartment.uuid: apartment for apartment in apartments}
    for apartment_data in apartments_data:
        expect_apartment_data = apartments[apartment_data["apartment_uuid"]]
        assert (
            apartment_data["apartment_number"] == expect_apartment_data.apartment_number
        )
        assert (
            apartment_data["apartment_structure"]
            == expect_apartment_data.apartment_structure
        )
        assert apartment_data["living_area"] == expect_apartment_data.living_area

        assert apartment_data["reservations"]
        assert (
            len(apartment_data["reservations"])
            == expect_reservations_per_apartment_count
        )
        expect_sorted_reservations = sorted(
            apartment_data["reservations"],
            key=lambda x: (x["lottery_position"], x["queue_position"]),
        )
        assert apartment_data["reservations"] == expect_sorted_reservations
