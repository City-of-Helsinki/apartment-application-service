import pytest
import uuid
from django.urls import reverse
from urllib.parse import urlencode

from apartment.elastic.queries import get_project
from apartment.models import ProjectExtraData
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models import ApartmentReservation
from application_form.services.application import cancel_reservation
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from customer.tests.factories import CustomerFactory
from users.tests.utils import assert_customer_match_data


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_apartment_list_get(salesperson_api_client):
    response = salesperson_api_client.get(
        reverse("apartment:apartment-list"), format="json"
    )
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
def test_apartment_list_get_with_project_uuid(
    salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    data = {"project_uuid": project_uuid}
    response = salesperson_api_client.get(
        reverse("apartment:apartment-list"),
        data=data,
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == 5
    assert response.data[0].get("uuid") == apartments[0].uuid


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_list_get(salesperson_api_client):
    response = salesperson_api_client.get(
        reverse("apartment:project-list"), format="json"
    )
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["list", "detail"])
@pytest.mark.parametrize("lottery_exists", (True, False))
def test_project_list_lottery_completed_field(
    salesperson_api_client, elastic_project_with_5_apartments, endpoint, lottery_exists
):
    project_uuid, apartments = elastic_project_with_5_apartments

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
    response = salesperson_api_client.get(url, format="json")
    assert response.status_code == 200

    data = response.data[0] if endpoint == "list" else response.data
    assert data["lottery_completed"] is lottery_exists


@pytest.mark.django_db
def test_project_get_with_project_uuid(
    salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, _ = elastic_project_with_5_apartments
    response = salesperson_api_client.get(
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
def test_project_get_with_project_uuid_not_exist(salesperson_api_client):
    response = salesperson_api_client.get(
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

        if (
            reservation["state"] == ApartmentReservationState.CANCELED.value
            and reservation_obj.state_change_events.count() > 0
        ):
            assert reservation["cancellation_reason"] is not None
            assert reservation["cancellation_timestamp"] is not None


@pytest.mark.django_db
def test_project_detail_apartment_reservations(
    salesperson_api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5
    expect_reservations_per_apartment_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        for i in range(0, expect_reservations_per_apartment_count):
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid,
                list_position=i + 1,
                state=ApartmentReservationState.SUBMITTED,
            )

    response = salesperson_api_client.get(
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

        _assert_apartment_reservations_data(apartment_data["reservations"])
        for reservation_data in apartment_data["reservations"]:
            assert_customer_match_data(
                ApartmentReservation.objects.get(id=reservation_data["id"]).customer,
                reservation_data["customer"],
                compact=True,
            )


@pytest.mark.django_db
def test_project_detail_apartment_reservations_has_children(
    salesperson_api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=1,
            state=ApartmentReservationState.SUBMITTED,
        )
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=2,
            application_apartment=None,
            state=ApartmentReservationState.SUBMITTED,
        )
    response = salesperson_api_client.get(
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
    salesperson_api_client, elastic_project_with_5_apartments
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
    response = salesperson_api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200
    apartments_data = response.data["apartments"]
    for apartment_data in apartments_data:
        for reservation in apartment_data["reservations"]:
            assert reservation["has_multiple_winning_apartments"] == (
                reservation["customer"]["id"] == customer.id
            )


@pytest.mark.django_db
def test_export_applicants_csv_per_project(
    salesperson_api_client, elastic_project_with_5_apartments
):
    """
    Test export applicants information to CSV
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    project = get_project(project_uuid)

    data = {"project_uuid": uuid.uuid4()}
    response = salesperson_api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.status_code == 404

    data = {"project_uuid": project_uuid}
    response = salesperson_api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.headers["Content-Type"] == "text/csv"
    assert (
        project.project_street_address.replace(" ", "_")
        in response.headers["Content-Disposition"]
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_export_lottery_result_csv_per_project(
    salesperson_api_client, elastic_project_with_5_apartments
):
    """
    Test export applicants information to CSV
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    project = get_project(project_uuid)

    data = {"project_uuid": uuid.uuid4()}
    response = salesperson_api_client.get(
        reverse("apartment:project-detail-lottery-result", kwargs=data),
        format="json",
    )
    assert response.status_code == 404

    data = {"project_uuid": project_uuid}
    response = salesperson_api_client.get(
        reverse("apartment:project-detail-lottery-result", kwargs=data),
        format="json",
    )
    assert response.status_code == 400
    assert "lottery has not happened" in str(response.data)

    app = ApplicationFactory()
    app.application_apartments.create(
        apartment_uuid=apartments[0].uuid, priority_number=1
    )
    add_application_to_queues(app)
    distribute_apartments(project_uuid)
    response = salesperson_api_client.get(
        reverse("apartment:project-detail-lottery-result", kwargs=data),
        format="json",
    )
    assert response.headers["Content-Type"] == "text/csv"
    assert (
        project.project_street_address.replace(" ", "_")
        in response.headers["Content-Disposition"]
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_project_detail_apartment_states(
    salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    apartments = sorted(apartments, key=lambda x: x["uuid"])

    # first apartment
    ApartmentReservationFactory(
        apartment_uuid=apartments[0].uuid,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.SUBMITTED,
    )

    # second apartment
    LotteryEventFactory(apartment_uuid=apartments[1].uuid)

    # third apartment
    ApartmentReservationFactory(
        apartment_uuid=apartments[2].uuid,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.RESERVED,
    )
    ApartmentReservationFactory(
        apartment_uuid=apartments[2].uuid,
        queue_position=2,
        list_position=2,
        state=ApartmentReservationState.SUBMITTED,
    )
    LotteryEventFactory(apartment_uuid=apartments[2].uuid)

    # fourth apartment
    ApartmentReservationFactory(
        apartment_uuid=apartments[3].uuid,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.OFFERED,
    )
    ApartmentReservationFactory(
        apartment_uuid=apartments[3].uuid,
        queue_position=2,
        list_position=2,
        state=ApartmentReservationState.SUBMITTED,
    )
    LotteryEventFactory(apartment_uuid=apartments[3].uuid)

    # fifth apartment
    ApartmentReservationFactory(
        apartment_uuid=apartments[4].uuid,
        queue_position=None,
        list_position=1,
        state=ApartmentReservationState.CANCELED,
    )
    ApartmentReservationFactory(
        apartment_uuid=apartments[4].uuid,
        queue_position=1,
        list_position=2,
        state=ApartmentReservationState.OFFER_ACCEPTED,
    )
    LotteryEventFactory(apartment_uuid=apartments[4].uuid)

    response = salesperson_api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200

    states = [
        a["state"]
        for a in sorted(response.data["apartments"], key=lambda x: x["apartment_uuid"])
    ]
    assert states == [
        "free",
        "free",
        "reserved",
        "offered",
        "offer_accepted",
    ]


@pytest.mark.django_db
def test_project_detail_apartment_reservations_has_cancellation_info(
    salesperson_api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=1,
            state=ApartmentReservationState.SUBMITTED,
        )
        cancelled_reservation = ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=2,
            application_apartment=None,
        )
        cancel_reservation(
            cancelled_reservation,
            cancellation_reason=ApartmentReservationCancellationReason.CANCELED.value,
        )

    response = salesperson_api_client.get(
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
def test_export_sale_report(salesperson_api_client, elastic_project_with_5_apartments):
    """
    Test export applicants information to CSV
    """
    project_uuid, apartments = elastic_project_with_5_apartments

    response = salesperson_api_client.get(
        reverse("apartment:sale-report"),
        format="json",
    )
    assert response.status_code == 400
    assert "Missing start date or end date" in str(response.data)
    base_url = reverse("apartment:sale-report")
    query_params = {
        "start_date": "1990-22-12",
        "end_date": "1990-22-12",
    }
    response = salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert response.status_code == 400
    assert "Invalid datetime format" in str(response.data)

    query_params = {
        "start_date": "1990-02-12",
        "end_date": "1990-01-12",
    }
    response = salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert response.status_code == 400
    assert "greater than" in str(response.data)

    query_params = {
        "start_date": "2020-02-12",
        "end_date": "2020-03-12",
    }
    response = salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert response.headers["Content-Type"] == "text/csv"
    assert response.status_code == 200


def _build_url_with_query_params(base_url, query_params):
    return "{}?{}".format(base_url, urlencode(query_params))


@pytest.mark.django_db
@pytest.mark.parametrize("has_extra_data_instance", (False, True))
def test_get_project_extra_data_endpoint(
    salesperson_api_client, has_extra_data_instance
):
    apartment = ApartmentDocumentFactory()
    project_uuid = apartment.project_uuid

    if has_extra_data_instance:
        ProjectExtraData.objects.create(
            project_uuid=project_uuid,
            offer_message_intro="test intro",
            offer_message_content="test content",
        )

    url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})

    response = salesperson_api_client.get(url, format="json")
    assert response.status_code == 200
    expected = (
        {"offer_message_intro": "test intro", "offer_message_content": "test content"}
        if has_extra_data_instance
        else {"offer_message_intro": "", "offer_message_content": ""}
    )
    assert response.data["extra_data"] == expected


@pytest.mark.django_db
@pytest.mark.parametrize("has_extra_data_instance", (False, True))
def test_put_project_extra_data_endpoint(
    salesperson_api_client, has_extra_data_instance
):
    apartment = ApartmentDocumentFactory()
    project_uuid = apartment.project_uuid

    if has_extra_data_instance:
        ProjectExtraData.objects.create(
            project_uuid=project_uuid,
            offer_message_intro="test intro",
            offer_message_content="test content",
        )

    data = {
        "offer_message_intro": "updated test intro",
        "offer_message_content": "updated test content",
    }

    url = reverse(
        "apartment:project-detail-extra-data", kwargs={"project_uuid": project_uuid}
    )

    response = salesperson_api_client.put(url, data=data, format="json")
    assert response.status_code == 200
    assert response.data == {
        "offer_message_intro": "updated test intro",
        "offer_message_content": "updated test content",
    }
    extra_data = ProjectExtraData.objects.get(project_uuid=project_uuid)
    assert extra_data.offer_message_intro == "updated test intro"
    assert extra_data.offer_message_content == "updated test content"


@pytest.mark.django_db
def test_get_project_extra_data_endpoint_non_existing_project(salesperson_api_client):
    ApartmentDocumentFactory()
    project_uuid = uuid.uuid4()

    url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})
    response = salesperson_api_client.get(url, format="json")

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("has_extra_data_instance", (False, True))
def test_get_project_detail_extra_data_field(
    salesperson_api_client, has_extra_data_instance
):
    apartment = ApartmentDocumentFactory()
    project_uuid = apartment.project_uuid

    if has_extra_data_instance:
        ProjectExtraData.objects.create(
            project_uuid=project_uuid,
            offer_message_intro="test intro",
            offer_message_content="test content",
        )

    url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})

    response = salesperson_api_client.get(url, format="json")
    assert response.status_code == 200
    expected = (
        {"offer_message_intro": "test intro", "offer_message_content": "test content"}
        if has_extra_data_instance
        else {"offer_message_intro": "", "offer_message_content": ""}
    )
    assert response.data["extra_data"] == expected
