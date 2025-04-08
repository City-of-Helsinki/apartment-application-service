import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import pytest
from django.urls import reverse

from apartment.elastic.queries import get_project, get_projects
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
    ApplicationApartmentFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from customer.tests.factories import CustomerFactory
from users.enums import UserKeyValueKeys
from users.tests.utils import assert_customer_match_data
from users.models import UserKeyValue


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_apartment_list_get_unauthorized(
    user_api_client, drupal_salesperson_api_client
):
    response = user_api_client.get(reverse("apartment:apartment-list"), format="json")
    assert response.status_code == 403

    response = drupal_salesperson_api_client.get(
        reverse("apartment:apartment-list"), format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_apartment_list_get(sales_ui_salesperson_api_client):
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:apartment-list"), format="json"
    )
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
def test_apartment_list_get_with_project_uuid(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:apartment-list"),
        data=data,
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data) == 5
    assert response.data[0].get("uuid") == apartments[0].uuid


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_list_get_unauthorized(user_api_client):
    response = user_api_client.get(reverse("apartment:project-list"), format="json")
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_project_list_get(sales_ui_salesperson_api_client):
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-list"), format="json"
    )
    assert response.status_code == 200
    assert len(response.data) > 0


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_selected_project_list_get_unauthorized(user_api_client):
    response = user_api_client.get(reverse("apartment:report-selected-project-list"), format="json")
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_selected_project_list_get(sales_ui_salesperson_api_client, 
                                   elastic_project_with_5_apartments,
    ):
    project_uuid, apartments = elastic_project_with_5_apartments

    all_projects = get_projects()
    # should initially return all projects when there are no projects saved yet
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:report-selected-project-list"), format="json"
    )
    assert response.status_code == 200
    assert len(response.data) == len(get_projects())

    UserKeyValue.objects.create(
        user=sales_ui_salesperson_api_client.user,
        key=UserKeyValueKeys.INCLUDE_SALES_REPORT_PROJECT_UUID.value,
        value=project_uuid
    )

    # should only return saved project_uuids
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:report-selected-project-list"), format="json" 
    )
    assert response.status_code == 200
    assert project_uuid in [p["uuid"] for p in response.data]



@pytest.mark.django_db
@pytest.mark.parametrize("lottery_exists", (True, False))
def test_project_detail_lottery_completed_at_field(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments, lottery_exists
):
    project_uuid, apartments = elastic_project_with_5_apartments

    if lottery_exists:
        lottery_event = LotteryEventFactory(apartment_uuid=apartments[0].uuid)

    url = reverse(
        "apartment:project-detail",
        kwargs={"project_uuid": project_uuid},
    )
    response = sales_ui_salesperson_api_client.get(url, format="json")
    assert response.status_code == 200

    assert response.data["lottery_completed_at"] == (
        lottery_event.timestamp if lottery_exists else None
    )


@pytest.mark.django_db
@pytest.mark.parametrize("applications_exist", (True, False))
def test_project_detail_application_count_field(
    sales_ui_salesperson_api_client,
    elastic_project_with_5_apartments,
    applications_exist,
):
    project_uuid, apartments = elastic_project_with_5_apartments

    if applications_exist:
        # two applications, the first one is for two apartments which should not matter
        application_1 = ApplicationFactory()
        ApplicationApartmentFactory(
            application=application_1,
            apartment_uuid=apartments[0].uuid,
            priority_number=1,
        )
        ApplicationApartmentFactory(
            application=application_1,
            apartment_uuid=apartments[1].uuid,
            priority_number=2,
        )
        application_2 = ApplicationFactory()
        ApplicationApartmentFactory(
            application=application_2,
            apartment_uuid=apartments[2].uuid,
            priority_number=1,
        )

    # another project application that should not be counted
    ApplicationApartmentFactory()

    url = reverse(
        "apartment:project-detail",
        kwargs={"project_uuid": project_uuid},
    )
    response = sales_ui_salesperson_api_client.get(url, format="json")
    assert response.status_code == 200

    assert response.data["application_count"] == (2 if applications_exist else 0)


@pytest.mark.django_db
def test_project_get_with_project_uuid_unauthorized(
    user_api_client, elastic_project_with_5_apartments
):
    project_uuid, _ = elastic_project_with_5_apartments
    response = user_api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_project_get_with_project_uuid(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, _ = elastic_project_with_5_apartments
    response = sales_ui_salesperson_api_client.get(
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
def test_project_get_with_project_uuid_not_exist(sales_ui_salesperson_api_client):
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": uuid.uuid4()}),
        format="json",
    )
    assert response.status_code == 404


def _assert_apartment_reservations_data(reservations):
    for reservation in reservations:
        assert "priority_number" in reservation
        assert "has_children" in reservation
        reservation_obj = ApartmentReservation.objects.get(pk=reservation["id"])

        if (
            reservation["state"] == ApartmentReservationState.CANCELED.value
            and reservation_obj.state_change_events.count() > 0
        ):
            assert reservation["cancellation_reason"] is not None
            assert reservation["cancellation_timestamp"] is not None


@pytest.mark.django_db
def test_project_detail_apartment_reservations(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=1,
            queue_position=None,
            state=ApartmentReservationState.CANCELED,
        )
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=2,
            queue_position=1,
            state=ApartmentReservationState.RESERVED,
        )
        for i in range(2, 5):
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid,
                list_position=i + 1,
                queue_position=i,
                state=ApartmentReservationState.SUBMITTED,
            )

    response = sales_ui_salesperson_api_client.get(
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
        assert apartment_data["reservation_count"] == 4

        _assert_apartment_reservations_data([apartment_data["winning_reservation"]])
        assert_customer_match_data(
            ApartmentReservation.objects.get(
                id=apartment_data["winning_reservation"]["id"]
            ).customer,
            apartment_data["winning_reservation"]["customer"],
            compact=True,
        )
        assert apartment_data["winning_reservation"]["state"] == "reserved"


@pytest.mark.django_db
def test_project_detail_apartment_reservations_has_children(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    expect_apartments_count = 5

    project_uuid, apartments = elastic_project_with_5_apartments
    for apartment in apartments:
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=1,
            queue_position=1,
            state=ApartmentReservationState.SUBMITTED,
        )
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=2,
            queue_position=2,
            application_apartment=None,
            state=ApartmentReservationState.SUBMITTED,
        )
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200
    assert response.data

    assert response.data["apartments"]
    apartments_data = response.data["apartments"]
    assert len(apartments_data) == expect_apartments_count

    for apartment_data in apartments_data:
        _assert_apartment_reservations_data([apartment_data["winning_reservation"]])


@pytest.mark.django_db
def test_project_detail_apartment_reservations_multiple_winning(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    customer = CustomerFactory()
    app1 = ApplicationFactory(
        type=ApplicationType.HITAS, customer=customer, has_children=False
    )
    app2 = ApplicationFactory(type=ApplicationType.HITAS)

    high_priority_app = ApplicationFactory(
        type=ApplicationType.HITAS, has_children=True
    )

    # Customer of app1 will win the apartments[1]
    # (apartments[0] will be cancelled due to lower priority)
    app1.application_apartments.create(
        apartment_uuid=apartments[0].uuid, priority_number=3
    )
    app1.application_apartments.create(
        apartment_uuid=apartments[1].uuid, priority_number=2
    )
    app1.application_apartments.create(
        apartment_uuid=apartments[2].uuid, priority_number=1
    )
    # Higher priority wins the apartments[2]
    high_priority_app.application_apartments.create(
        apartment_uuid=apartments[2].uuid, priority_number=1
    )

    # Customer of app2 win apartments[3]
    app2.application_apartments.create(
        apartment_uuid=apartments[3].uuid, priority_number=1
    )

    add_application_to_queues(app1)
    add_application_to_queues(app2)
    add_application_to_queues(high_priority_app)
    distribute_apartments(project_uuid)
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid}),
        format="json",
    )
    assert response.status_code == 200
    apartments_data = response.data["apartments"]
    for apartment_data in apartments_data:
        if apartment_data["winning_reservation"]:
            assert not apartment_data["winning_reservation"][
                "has_multiple_winning_apartments"
            ]


@pytest.mark.django_db
def test_apartment_detail_reservations(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments
    apartment = apartments[0]

    cancelled_reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        list_position=1,
        application_apartment=None,
        state=ApartmentReservationState.SUBMITTED,
    )
    cancel_reservation(
        cancelled_reservation,
        cancellation_reason=ApartmentReservationCancellationReason.CANCELED.value,
    )

    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        list_position=2,
        queue_position=1,
        state=ApartmentReservationState.RESERVED,
    )
    for i in range(2, 5):
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            list_position=i + 1,
            queue_position=i,
            state=ApartmentReservationState.SUBMITTED,
        )

    # another apartment, should not be returned
    ApartmentReservationFactory(
        apartment_uuid=apartments[1].uuid,
        list_position=1,
        queue_position=1,
        state=ApartmentReservationState.RESERVED,
    )
    # another apartment, should not be returned
    ApartmentReservationFactory(
        apartment_uuid=apartments[1].uuid,
        list_position=2,
        queue_position=2,
        state=ApartmentReservationState.SUBMITTED,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "apartment:apartment-detail-reservations-list",
            kwargs={"apartment_uuid": apartment.uuid},
        ),
        format="json",
    )
    assert response.status_code == 200
    reservation_data = response.data
    assert len(reservation_data) == 5

    _assert_apartment_reservations_data(reservation_data)


@pytest.mark.django_db
def test_export_applicants_csv_per_project_unauthorized(
    user_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments

    data = {"project_uuid": uuid.uuid4()}
    response = user_api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_export_applicants_csv_per_project(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    """
    Test export applicants information to CSV
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    project = get_project(project_uuid)

    data = {"project_uuid": uuid.uuid4()}
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.status_code == 404

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail-export-applicant", kwargs=data),
        format="json",
    )
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8-sig"
    assert (
        project.project_street_address.replace(" ", "_")
        in response.headers["Content-Disposition"]
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_export_lottery_result_csv_per_project_unauthorized(
    user_api_client, elastic_project_with_5_apartments
):
    project_uuid, apartments = elastic_project_with_5_apartments

    app = ApplicationFactory()
    app.application_apartments.create(
        apartment_uuid=apartments[0].uuid, priority_number=1
    )
    add_application_to_queues(app)
    distribute_apartments(project_uuid)

    data = {"project_uuid": project_uuid}
    response = user_api_client.get(
        reverse("apartment:project-detail-lottery-result", kwargs=data),
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_export_lottery_result_csv_per_project(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
):
    """
    Test export applicants information to CSV
    """
    project_uuid, apartments = elastic_project_with_5_apartments
    project = get_project(project_uuid)

    data = {"project_uuid": uuid.uuid4()}
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail-lottery-result", kwargs=data),
        format="json",
    )
    assert response.status_code == 404

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.get(
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
    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-detail-lottery-result", kwargs=data),
        format="json",
    )
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8-sig"
    assert (
        project.project_street_address.replace(" ", "_")
        in response.headers["Content-Disposition"]
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_project_detail_apartment_states(
    sales_ui_salesperson_api_client, elastic_project_with_5_apartments
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

    response = sales_ui_salesperson_api_client.get(
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
def test_export_sale_report_unauthorized(
    user_api_client, elastic_project_with_5_apartments
):
    query_params = {
        "start_date": "2020-02-12",
        "end_date": "2020-03-12",
    }
    response = user_api_client.get(
        _build_url_with_query_params(reverse("apartment:sale-report"), query_params),
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_export_sale_report(
    sales_ui_salesperson_api_client,
    elastic_project_with_5_apartments,
):
    """
    Test export applicants information to CSV
    """
    export_project_uuid, export_apartments = elastic_project_with_5_apartments

    response = sales_ui_salesperson_api_client.get(
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
    response = sales_ui_salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert response.status_code == 400
    assert "Invalid datetime format" in str(response.data)

    query_params = {
        "start_date": "1990-02-12",
        "end_date": "1990-01-12",
    }
    response = sales_ui_salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert response.status_code == 400
    assert "greater than" in str(response.data)

    query_params = {
        "start_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "end_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "project_uuids": export_project_uuid,
    }

    response = sales_ui_salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert (
        response.headers["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )  # noqa: E501
    assert response.status_code == 200
    assert (
        f"{query_params['start_date']}_-_{query_params['end_date']}.xlsx"
        in response.get("Content-Disposition")
    )

    # all_project_uuids = [p.project_uuid for p in get_projects()]
    # project_uuids_to_exclude = set(all_project_uuids).difference(set([export_project_uuid]))

    # new UUID should have been added to sales report UUIDs
    assert UserKeyValue.objects.user_key_values(
        user=sales_ui_salesperson_api_client.user,
        key=UserKeyValueKeys.INCLUDE_SALES_REPORT_PROJECT_UUID.value
    ).filter(value=export_project_uuid).count() == 1

    # UUID should be removed from sales report UUIDs if its not included in query params
    query_params = {
        "start_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "end_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "project_uuids": uuid.uuid4(),
    }

    response = sales_ui_salesperson_api_client.get(
        _build_url_with_query_params(base_url, query_params), format="json"
    )
    assert UserKeyValue.objects.user_key_values(
        user=sales_ui_salesperson_api_client.user,
        key=UserKeyValueKeys.INCLUDE_SALES_REPORT_PROJECT_UUID.value
    ).filter(value=export_project_uuid).count() == 0


def _build_url_with_query_params(base_url, query_params):
    return "{}?{}".format(base_url, urlencode(query_params))


@pytest.mark.django_db
def test_get_project_extra_data_endpoint_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    project_uuid = apartment.project_uuid

    url = reverse(
        "apartment:project-detail-extra-data", kwargs={"project_uuid": project_uuid}
    )

    response = user_api_client.get(url, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("has_extra_data_instance", (False, True))
def test_get_project_extra_data_endpoint(
    sales_ui_salesperson_api_client, has_extra_data_instance
):
    apartment = ApartmentDocumentFactory()
    project_uuid = apartment.project_uuid

    if has_extra_data_instance:
        ProjectExtraData.objects.create(
            project_uuid=project_uuid,
            offer_message_intro="test intro",
            offer_message_content="test content",
        )

    url = reverse(
        "apartment:project-detail-extra-data", kwargs={"project_uuid": project_uuid}
    )

    response = sales_ui_salesperson_api_client.get(url, format="json")
    assert response.status_code == 200
    expected = (
        {"offer_message_intro": "test intro", "offer_message_content": "test content"}
        if has_extra_data_instance
        else {"offer_message_intro": "", "offer_message_content": ""}
    )
    assert response.data == expected


@pytest.mark.django_db
def test_put_project_extra_data_endpoint_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    project_uuid = apartment.project_uuid

    data = {
        "offer_message_intro": "updated test intro",
        "offer_message_content": "updated test content",
    }

    url = reverse(
        "apartment:project-detail-extra-data", kwargs={"project_uuid": project_uuid}
    )

    response = user_api_client.put(url, data=data, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("has_extra_data_instance", (False, True))
def test_put_project_extra_data_endpoint(
    sales_ui_salesperson_api_client, has_extra_data_instance
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

    response = sales_ui_salesperson_api_client.put(url, data=data, format="json")
    assert response.status_code == 200
    assert response.data == {
        "offer_message_intro": "updated test intro",
        "offer_message_content": "updated test content",
    }
    extra_data = ProjectExtraData.objects.get(project_uuid=project_uuid)
    assert extra_data.offer_message_intro == "updated test intro"
    assert extra_data.offer_message_content == "updated test content"


@pytest.mark.django_db
def test_get_project_extra_data_endpoint_non_existing_project(
    sales_ui_salesperson_api_client,
):
    ApartmentDocumentFactory()
    project_uuid = uuid.uuid4()

    url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})
    response = sales_ui_salesperson_api_client.get(url, format="json")

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("has_extra_data_instance", (False, True))
def test_get_project_detail_extra_data_field(
    sales_ui_salesperson_api_client, has_extra_data_instance
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

    response = sales_ui_salesperson_api_client.get(url, format="json")
    assert response.status_code == 200
    expected = (
        {"offer_message_intro": "test intro", "offer_message_content": "test content"}
        if has_extra_data_instance
        else {"offer_message_intro": "", "offer_message_content": ""}
    )
    assert response.data["extra_data"] == expected
