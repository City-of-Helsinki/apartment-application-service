import pytest
from datetime import datetime
from django.urls import reverse
from rest_framework import status

from application_form import error_codes
from application_form.tests.conftest import create_application_data
from audit_log.models import AuditLog
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
def test_application_post(api_client, elastic_single_project_with_apartments):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201
    assert response.data == {"application_uuid": data["application_uuid"]}


@pytest.mark.django_db
def test_application_post_writes_audit_log(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    api_client.post(reverse("application_form:application-list"), data, format="json")
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "USER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "CREATE"
    assert audit_event["target"] == {
        "id": data["application_uuid"],
        "type": "Application",
    }
    assert audit_event["status"] == "SUCCESS"


@pytest.mark.django_db
def test_application_post_fails_if_not_authenticated(
    api_client, elastic_single_project_with_apartments
):
    data = create_application_data(ProfileFactory())
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_application_post_writes_audit_log_if_not_authenticated(
    api_client, elastic_single_project_with_apartments
):
    data = create_application_data(ProfileFactory())
    api_client.post(reverse("application_form:application-list"), data, format="json")
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert audit_event["operation"] == "CREATE"
    assert audit_event["target"] == {"id": None, "type": "Application"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
def test_application_post_fails_if_applicant_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if single applicant tries to send multiple applications. Only
    one application is allowed per project.
    """
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    application_data = create_application_data(profile, num_applicants=1)
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.django_db
def test_application_post_fails_if_applicants_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if applicants tries to send multiple applications. Only one
    application is allowed per project.
    """
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    application_data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.django_db
def test_application_post_fails_if_partner_applicant_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if same partner has set into two different applications. Only one
    application is allowed per project.
    """
    profile = ProfileFactory()
    application_data = create_application_data(profile)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    second_profile = ProfileFactory()
    second_application_data = create_application_data(second_profile)
    second_application_data["additional_applicant"]["ssn_suffix"] = application_data[
        "additional_applicant"
    ]["ssn_suffix"]
    second_application_data["additional_applicant"]["date_of_birth"] = application_data[
        "additional_applicant"
    ]["date_of_birth"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(second_profile)}")
    response = api_client.post(
        reverse("application_form:application-list"),
        second_application_data,
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0


@pytest.mark.django_db
def test_application_post_fails_if_partner_profile_have_already_applied_to_project(
    api_client, elastic_single_project_with_apartments
):
    """
    Tests that if partner tries to use own profile in another application. Only one
    application is allowed per project.
    """
    profile = ProfileFactory()
    application_data = create_application_data(profile)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.post(
        reverse("application_form:application-list"), application_data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    partner_profile = ProfileFactory(
        date_of_birth=datetime.strptime(
            application_data["additional_applicant"]["date_of_birth"], "%Y-%m-%d"
        ).date(),
    )
    partner_application_data = create_application_data(partner_profile)
    partner_application_data["ssn_suffix"] = application_data["additional_applicant"][
        "ssn_suffix"
    ]
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(partner_profile)}"
    )
    response = api_client.post(
        reverse("application_form:application-list"),
        partner_application_data,
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED
    assert len(response.data["message"]) > 0
