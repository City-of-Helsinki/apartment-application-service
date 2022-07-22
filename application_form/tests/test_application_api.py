import pytest
from datetime import datetime
from django.urls import reverse
from rest_framework import status

from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form import error_codes
from application_form.enums import ApplicationArrivalMethod, ApplicationType
from application_form.models import Application
from application_form.tests.conftest import create_application_data
from application_form.tests.factories import (
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from audit_log.models import AuditLog
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.models import Profile
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


@pytest.mark.parametrize("already_existing_customer", (False, True))
@pytest.mark.django_db
def test_application_post_single_profile_customer(
    api_client, elastic_single_project_with_apartments, already_existing_customer
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    assert Profile.objects.count() == 1
    if already_existing_customer:
        apartment = ApartmentDocumentFactory()
        application = ApplicationFactory(
            customer=CustomerFactory(primary_profile=profile),
        )
        ApplicationApartmentFactory.create_application_with_apartments(
            [apartment.uuid], application
        )
        assert Customer.objects.count() == 1
    else:
        assert Customer.objects.count() == 0

    data = create_application_data(profile, num_applicants=1)

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == profile.id

    assert Profile.objects.count() == 1
    assert Customer.objects.count() == 1
    assert application.customer.secondary_profile is None


@pytest.mark.parametrize("already_existing_customer", (False, True, "wrong"))
@pytest.mark.django_db
def test_application_post_multi_profile_customer(
    api_client, elastic_single_project_with_apartments, already_existing_customer
):
    profile = ProfileFactory()
    secondary_profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    if already_existing_customer:
        apartment = ApartmentDocumentFactory()
        if already_existing_customer is True:
            application = ApplicationFactory(
                customer=CustomerFactory(
                    primary_profile=profile, secondary_profile=secondary_profile
                ),
            )
        else:
            application = ApplicationFactory(
                customer=CustomerFactory(
                    primary_profile=profile, secondary_profile=ProfileFactory()
                ),
            )
        ApplicationApartmentFactory.create_application_with_apartments(
            [apartment.uuid], application
        )
        assert Customer.objects.count() == 1
    else:
        assert Customer.objects.count() == 0
    assert Profile.objects.count() == 3 if already_existing_customer == "wrong" else 2

    data = create_application_data(profile)
    if already_existing_customer is True:
        data["additional_applicant"][
            "date_of_birth"
        ] = f"{secondary_profile.date_of_birth:%Y-%m-%d}"
        data["additional_applicant"]["ssn_suffix"] = secondary_profile.ssn_suffix

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == profile.id
    if already_existing_customer is True:
        assert str(application.customer.secondary_profile_id) == secondary_profile.id
    else:
        assert application.customer.secondary_profile


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
def test_application_post_fails_if_incorrect_ssn_suffix(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    data["ssn_suffix"] = "-000$"
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(response.data["ssn_suffix"][0]["message"]) > 0
    assert (
        response.data["ssn_suffix"][0]["code"]
        == error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID
    )


@pytest.mark.django_db
def test_application_post_fails_if_incorrect_ssn_suffix_additional_applicant(
    api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    data["additional_applicant"]["ssn_suffix"] = "-000$"
    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(response.data["additional_applicant"]["ssn_suffix"][0]["message"]) > 0
    assert (
        response.data["additional_applicant"]["ssn_suffix"][0]["code"]
        == error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID
    )


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


@pytest.mark.parametrize(
    "application_type", (ApplicationType.HITAS, ApplicationType.HASO)
)
@pytest.mark.django_db
def test_application_post_generate_metadata(
    api_client, elastic_single_project_with_apartments, application_type
):
    profile = ProfileFactory()
    secondary_profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    apartment = ApartmentDocumentFactory()
    application = ApplicationFactory(
        customer=CustomerFactory(
            primary_profile=profile, secondary_profile=secondary_profile
        ),
        type=application_type,
    )
    ApplicationApartmentFactory.create_application_with_apartments(
        [apartment.uuid], application
    )

    data = create_application_data(profile, application_type=application_type)
    data["additional_applicant"][
        "date_of_birth"
    ] = f"{secondary_profile.date_of_birth:%Y-%m-%d}"
    data["additional_applicant"]["ssn_suffix"] = secondary_profile.ssn_suffix
    data["additional_applicant"]["first_name"] = secondary_profile.first_name
    data["additional_applicant"]["last_name"] = secondary_profile.last_name

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )
    assert response.status_code == 201, response.data
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert application.handler_information == METADATA_HANDLER_INFORMATION
    assert application.type == application_type
    assert (
        application.process_number == METADATA_HASO_PROCESS_NUMBER
        if application_type == ApplicationType.HASO
        else METADATA_HITAS_PROCESS_NUMBER
    )
    assert application.sender_names == "{}/ {}".format(
        profile.full_name, secondary_profile.full_name
    )
    assert application.method_of_arrival == ApplicationArrivalMethod.ELECTRONICAL_SYSTEM
