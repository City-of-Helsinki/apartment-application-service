import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.settings import METADATA_HANDLER_INFORMATION
from application_form.enums import ApplicationType
from application_form.models import ApartmentReservation, LotteryEvent
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import ApplicationFactory


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_without_project_uuid(
    sales_ui_salesperson_api_client,
):
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_badly_formatted_project_uuid(
    sales_ui_salesperson_api_client,
):
    data = {"project_uuid": "lizard"}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_fails_application_time_not_finished(
    sales_ui_salesperson_api_client, elastic_project_application_time_active
):
    project_uuid, apartment = elastic_project_application_time_active

    app = ApplicationFactory(type=ApplicationType.HITAS)
    app.application_apartments.create(apartment_uuid=apartment.uuid, priority_number=0)
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.json()[0]["message"] == "Project's application time is not finished."
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_not_found(sales_ui_salesperson_api_client):
    data = {"project_uuid": 1234}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_execute_hitas_lottery_for_project_post_unauthorized(
    user_api_client, elastic_hitas_project_application_end_time_finished
):
    project_uuid, apartment = elastic_hitas_project_application_end_time_finished

    app = ApplicationFactory(type=ApplicationType.HITAS)
    app.application_apartments.create(apartment_uuid=apartment.uuid, priority_number=0)
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = user_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_execute_hitas_lottery_for_project_post(
    sales_ui_salesperson_api_client, elastic_hitas_project_application_end_time_finished
):
    project_uuid, apartment = elastic_hitas_project_application_end_time_finished

    app = ApplicationFactory(type=ApplicationType.HITAS)
    app.application_apartments.create(apartment_uuid=apartment.uuid, priority_number=0)
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_execute_hitas_lottery_for_project_post_without_applications(
    sales_ui_salesperson_api_client, elastic_hitas_project_with_5_apartments
):
    project_uuid, apartments = elastic_hitas_project_with_5_apartments

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_execute_haso_lottery_for_project_post_unauthorized(
    user_api_client, elastic_haso_project_application_end_time_finished
):
    project_uuid, apartment = elastic_haso_project_application_end_time_finished

    app = ApplicationFactory(type=ApplicationType.HASO)
    app.application_apartments.create(apartment_uuid=apartment.uuid, priority_number=0)
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = user_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_execute_haso_lottery_for_project_post(
    sales_ui_salesperson_api_client, elastic_haso_project_application_end_time_finished
):
    project_uuid, apartment = elastic_haso_project_application_end_time_finished

    app = ApplicationFactory(type=ApplicationType.HASO)
    app.application_apartments.create(apartment_uuid=apartment.uuid, priority_number=0)
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_execute_haso_lottery_for_project_post_without_applications(
    sales_ui_salesperson_api_client, elastic_haso_project_with_5_apartments
):
    project_uuid, apartments = elastic_haso_project_with_5_apartments

    data = {"project_uuid": project_uuid}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "application_type", (ApplicationType.HASO, ApplicationType.HITAS)
)
@pytest.mark.django_db
def test_execute_lottery_generate_metadata(
    sales_ui_salesperson_api_client, application_type
):
    if application_type == ApplicationType.HASO:
        apartment = ApartmentDocumentFactory(
            project_ownership_type="Haso",
            project_application_end_time=timezone.now() - timedelta(days=1),
        )
    else:
        apartment = ApartmentDocumentFactory(
            project_ownership_type="Hitas",
            project_application_end_time=timezone.now() - timedelta(days=1),
        )

    app = ApplicationFactory(type=application_type)
    app.application_apartments.create(apartment_uuid=apartment.uuid, priority_number=0)
    add_application_to_queues(app)

    data = {"project_uuid": apartment.project_uuid}
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_200_OK

    lottery_event = LotteryEvent.objects.get(apartment_uuid=apartment.uuid)
    assert (
        lottery_event.handler
        == METADATA_HANDLER_INFORMATION
        + " / "
        + sales_ui_salesperson_api_client.user.profile_or_user_full_name
    )
    reservations = ApartmentReservation.objects.filter(apartment_uuid=apartment.uuid)
    for r in reservations:
        assert (
            r.handler == sales_ui_salesperson_api_client.user.profile_or_user_full_name
        )
