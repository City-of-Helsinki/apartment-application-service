import pytest
from django.urls import reverse
from rest_framework import status

from application_form.enums import ApplicationType
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import ApplicationFactory
from users.tests.factories import SalespersonProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_without_project_uuid(api_client):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_badly_formatted_project_uuid(api_client):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = {"project_uuid": "lizard"}
    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_execute_lottery_for_project_post_not_found(api_client):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = {"project_uuid": 1234}
    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_execute_hitas_lottery_for_project_post(
    api_client, elastic_hitas_project_with_5_apartments
):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    project_uuid, apartments = elastic_hitas_project_with_5_apartments

    app = ApplicationFactory(type=ApplicationType.HITAS)
    app.application_apartments.create(
        apartment_uuid=apartments[0].uuid, priority_number=0
    )
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_execute_hitas_lottery_for_project_post_without_applications(
    api_client, elastic_hitas_project_with_5_apartments
):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    project_uuid, apartments = elastic_hitas_project_with_5_apartments

    data = {"project_uuid": project_uuid}
    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_execute_haso_lottery_for_project_post(
    api_client, elastic_haso_project_with_5_apartments
):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    project_uuid, apartments = elastic_haso_project_with_5_apartments
    app = ApplicationFactory(type=ApplicationType.HASO)
    app.application_apartments.create(
        apartment_uuid=apartments[0].uuid, priority_number=0
    )
    add_application_to_queues(app)

    data = {"project_uuid": project_uuid}
    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_execute_haso_lottery_for_project_post_without_applications(
    api_client, elastic_haso_project_with_5_apartments
):
    profile = SalespersonProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    project_uuid, apartments = elastic_haso_project_with_5_apartments

    data = {"project_uuid": project_uuid}
    response = api_client.post(
        reverse("application_form:execute_lottery_for_project"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
