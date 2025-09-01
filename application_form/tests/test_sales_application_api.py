from datetime import datetime, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from django.urls import reverse

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form.enums import ApplicationArrivalMethod, ApplicationType
from application_form.models import ApartmentReservation
from application_form.models.application import Application
from application_form.tests.conftest import create_application_data
from application_form.tests.utils import assert_profile_match_data
from customer.models import Customer
from users.enums import Roles
from users.models import Profile
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
def test_sales_application_post_without_permission(
    sales_ui_salesperson_api_client, api_client, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    data = create_application_data(profile)
    response = sales_ui_salesperson_api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code == 403

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_sales_application_post(
    drupal_salesperson_api_client, elastic_single_project_with_apartments
):
    customer_profile = ProfileFactory()
    drupal_salesperson_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(drupal_salesperson_api_client.user.profile)}"  # noqa: E501
    )
    data = create_application_data(customer_profile)
    data["profile"] = customer_profile.id
    data["applicant"]["ssn_suffix"] = "XXXXX"  # ssn suffix should not be validated
    data["additional_applicant"]["ssn_suffix"] = "XXXXX"
    response = drupal_salesperson_api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code == 201
    assert response.data == {"application_uuid": data["application_uuid"]}

    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == customer_profile.id

    for reservation in ApartmentReservation.objects.all():
        assert (
            reservation.state_change_events.last().user
            == drupal_salesperson_api_client.user
        )


@pytest.mark.django_db
def test_sales_application_post_haso_submitted_late(
    api_client, elastic_hitas_project_with_5_apartments
):
    salesperson_profile = ProfileFactory()
    salesperson_group = Group.objects.get(name__iexact=Roles.DRUPAL_SALESPERSON.name)
    salesperson_group.user_set.add(salesperson_profile.user)

    customer_profile = ProfileFactory()
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(salesperson_profile)}"
    )

    application_start_time = (datetime.now() - timedelta(days=20)).replace(
        tzinfo=timezone.get_default_timezone()
    )
    application_end_time = application_start_time - timedelta(days=10)

    apartment = ApartmentDocumentFactory(
        project_application_start_time=application_start_time,
        project_application_end_time=application_end_time,
        project_ownership_type=OwnershipType.HASO.value,
        project_can_apply_afterwards=True
    )

    apartments_late_submit = [apartment]
    for idx in range(4):
        apt = ApartmentDocumentFactory(
            project_uuid=apartment.project_uuid,
            project_application_start_time=application_start_time,
            project_application_end_time=application_end_time,
            project_ownership_type=OwnershipType.HASO.value,
            project_can_apply_afterwards=True
        )

        apartments_late_submit.append(apt)

    late_submit_data = create_application_data(
        customer_profile, num_applicants=1, apartments=apartments_late_submit
    )

    late_submit_data["profile"] = customer_profile.id

    application = post_application(api_client, late_submit_data)
    assert application.submitted_late is True

    #  setting submitted_late manually in POST shouldnt be allowed
    customer_profile_2 = ProfileFactory()

    data = create_application_data(
        customer_profile_2, num_applicants=2, apartments=apartments_late_submit
    )

    data["profile"] = customer_profile_2.id
    data["submitted_late"] = False

    second_application = post_application(api_client, data)
    assert second_application.submitted_late is True

    # Test that HITAS apartment late submit isn't allowed (should only work with HASO)
    apartment = ApartmentDocumentFactory(
        project_application_start_time=application_start_time,
        project_application_end_time=application_end_time,
        project_ownership_type=OwnershipType.HITAS.value,
    )

    apartments_late_submit_hitas = [apartment]
    for idx in range(4):
        apt = ApartmentDocumentFactory(
            project_uuid=apartment.project_uuid,
            project_application_start_time=application_start_time,
            project_application_end_time=application_end_time,
            project_ownership_type=OwnershipType.HASO.value,
        )

        apartments_late_submit_hitas.append(apt)

    customer_profile_3 = ProfileFactory()

    data = create_application_data(
        customer_profile_3, num_applicants=2, apartments=apartments_late_submit_hitas
    )
    data["profile"] = customer_profile_3.id
    response = api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code is not 201

    # Test that ApartmentDocument.project_can_apply_afterwards is respected
    apartment_cant_apply_afterwards = ApartmentDocumentFactory(
        project_application_start_time=application_start_time,
        project_application_end_time=application_end_time,
        project_ownership_type=OwnershipType.HASO.value,
        project_can_apply_afterwards=False
    )

    customer_profile_4 = ProfileFactory()
    data = create_application_data(
        customer_profile_4, num_applicants=2, apartments=[apartment_cant_apply_afterwards]
    )
    data["profile"] = customer_profile_4.id

    response = api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code is not 201
    pass


def post_application(client, data):
    response = client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code == 201
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.customer.primary_profile.id) == data["profile"]
    return application


@pytest.mark.django_db
def test_sales_application_post_check_customer(
    api_client, elastic_single_project_with_apartments
):
    salesperson_profile = ProfileFactory()
    salesperson_group = Group.objects.get(name__iexact=Roles.DRUPAL_SALESPERSON.name)
    salesperson_group.user_set.add(salesperson_profile.user)

    customer_profile = ProfileFactory()
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(salesperson_profile)}"
    )
    assert Profile.objects.count() == 2
    assert Customer.objects.count() == 0

    # post an application with a single profile customer
    data = create_application_data(customer_profile, num_applicants=1)
    data["profile"] = customer_profile.id
    application = post_application(api_client, data)
    assert Profile.objects.count() == 2
    assert Customer.objects.count() == 1
    assert application.customer.secondary_profile is None

    # post an application with the same single profile customer
    data = create_application_data(customer_profile, num_applicants=1)
    data["profile"] = customer_profile.id
    application = post_application(api_client, data)
    assert Profile.objects.count() == 2
    assert Customer.objects.count() == 1
    assert application.customer.secondary_profile is None

    # post an application with a two profile customer
    data = create_application_data(customer_profile)
    data["profile"] = customer_profile.id
    application = post_application(api_client, data)
    assert Profile.objects.count() == 3
    assert Customer.objects.count() == 2
    assert_profile_match_data(
        application.customer.secondary_profile, data["additional_applicant"]
    )

    # post an application with the same two profile customer
    additional_applicant = data["additional_applicant"]
    data = create_application_data(customer_profile)
    data["profile"] = customer_profile.id
    data["additional_applicant"] = additional_applicant
    application = post_application(api_client, data)
    assert Profile.objects.count() == 3
    assert Customer.objects.count() == 2
    assert_profile_match_data(
        application.customer.secondary_profile, data["additional_applicant"]
    )

    # verify that a secondary profile is not matched if the primary does not match
    existing_secondary_profile = application.customer.secondary_profile
    another_profile = ProfileFactory()
    data = create_application_data(another_profile)
    data["profile"] = another_profile.id
    data["additional_applicant"] = additional_applicant
    application = post_application(api_client, data)
    assert Profile.objects.count() == 5
    assert Customer.objects.count() == 3
    assert_profile_match_data(
        application.customer.secondary_profile, data["additional_applicant"]
    )
    assert application.customer.secondary_profile != existing_secondary_profile

    # verify that another single profile customer is not matched
    data = create_application_data(another_profile, num_applicants=1)
    data["profile"] = another_profile.id
    application = post_application(api_client, data)
    assert Profile.objects.count() == 5
    assert Customer.objects.count() == 4
    assert application.customer.secondary_profile is None


@pytest.mark.parametrize(
    "application_type", (ApplicationType.HITAS, ApplicationType.HASO)
)
@pytest.mark.django_db
def test_sale_application_post_generate_metadata(
    api_client, elastic_single_project_with_apartments, application_type
):
    salesperson_profile = ProfileFactory()
    salesperson_group = Group.objects.get(name__iexact=Roles.DRUPAL_SALESPERSON.name)
    salesperson_group.user_set.add(salesperson_profile.user)

    customer_profile = ProfileFactory()
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(salesperson_profile)}"
    )
    assert Profile.objects.count() == 2
    assert Customer.objects.count() == 0

    # post an application with a two profile customer
    data = create_application_data(customer_profile, application_type=application_type)
    data["profile"] = customer_profile.id
    application = post_application(api_client, data)
    assert application.handler_information == METADATA_HANDLER_INFORMATION
    assert application.type == application_type
    assert (
        application.process_number == METADATA_HASO_PROCESS_NUMBER
        if application_type == ApplicationType.HASO
        else METADATA_HITAS_PROCESS_NUMBER
    )
    assert application.sender_names == "{}/ {}".format(
        customer_profile.full_name,
        data["additional_applicant"]["first_name"]
        + " "
        + data["additional_applicant"]["last_name"],
    )
    assert application.method_of_arrival == ApplicationArrivalMethod.POST
