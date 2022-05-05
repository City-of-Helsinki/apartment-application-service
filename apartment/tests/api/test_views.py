import pytest
import uuid
from django.urls import reverse

from apartment.elastic.queries import get_projects
from application_form.enums import ApplicationType
from application_form.models import ApartmentReservation
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from customer.tests.factories import CustomerFactory
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
    assert response.data.get("apartments")
    assert len(response.data.get("apartments")) == 5
    assert response.data.get("apartments")[0].get("url")


@pytest.mark.django_db
def test_project_get_with_project_uuid_not_exist(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": uuid.uuid4()}),
        format="json",
    )
    assert response.status_code == 404


def _assert_apartment_reservations_data(reservations):
    for reservation in reservations:
        assert "priority_number" in reservation
        assert "has_children" in reservation
        reservation_obj = ApartmentReservation.objects.get(pk=reservation["id"])
        if reservation_obj.application_apartment:
            assert (
                reservation["has_children"]
                == reservation_obj.application_apartment.application.has_children
            )
            assert (
                reservation["priority_number"]
                == reservation_obj.application_apartment.priority_number
            )
        else:
            assert reservation["has_children"] == reservation_obj.customer.has_children


@pytest.mark.django_db
def test_project_detail_apartment_reservations(
    api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5
    expect_reservations_per_apartment_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        for i in range(0, expect_reservations_per_apartment_count):
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid, list_position=i + 1
            )

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
            key=lambda x: (x["list_position"], x["queue_position"]),
        )
        assert apartment_data["reservations"] == expect_sorted_reservations

        _assert_apartment_reservations_data(apartment_data["reservations"])


@pytest.mark.django_db
def test_project_detail_apartment_reservations_has_children(
    api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        ApartmentReservationFactory(apartment_uuid=apartment.uuid, list_position=1)
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid, list_position=2, application_apartment=None
        )
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

    for apartment_data in apartments_data:
        assert apartment_data["reservations"]
        assert len(apartment_data["reservations"]) == 2
        _assert_apartment_reservations_data(apartment_data["reservations"])


@pytest.mark.django_db
def test_project_detail_apartment_reservations_multiple_winning(
    api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    customer = CustomerFactory()
    app1 = ApplicationFactory(type=ApplicationType.HITAS, customer=customer)
    app2 = ApplicationFactory(type=ApplicationType.HITAS)

    # Customer of app1 win 2 apartments
    app1.application_apartments.create(
        apartment_uuid=apartments[0].uuid, priority_number=1
    )
    app1.application_apartments.create(
        apartment_uuid=apartments[1].uuid, priority_number=1
    )
    # Customer of app2 win only 1 apartments
    app2.application_apartments.create(
        apartment_uuid=apartments[2].uuid, priority_number=1
    )
    add_application_to_queues(app1)
    add_application_to_queues(app2)
    distribute_apartments(project_uuid)
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200
    apartments_data = response.data["apartments"]
    for apartment_data in apartments_data:
        for reservation in apartment_data["reservations"]:
            assert reservation["has_multiple_winning_apartments"] == (
                reservation["customer"] == customer.id
            )


@pytest.mark.django_db
def test_export_applicants_csv_per_project(
    api_client, elastic_project_with_5_apartments
):
    """
    Test export applicants information to CSV
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    project = get_projects(project_uuid)[0]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = {"project_uuid": uuid.uuid4()}
    response = api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.status_code == 404

    data = {"project_uuid": project_uuid}
    response = api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.headers["Content-Type"] == "text/csv"
    assert (
        project.project_street_address.replace(" ", "_")
        in response.headers["Content-Disposition"]
    )
    assert response.status_code == 200
