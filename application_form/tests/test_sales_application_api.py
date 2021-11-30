import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from application_form.models import Application
from application_form.tests.utils import create_application_data
from users.enums import Roles
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_sales_application_post_without_permission(api_client):
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(profile)
    response = api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("elastic_apartments")
def test_sales_application_post(api_client):
    salesperson_profile = ProfileFactory()
    salesperson_group = Group.objects.get(name__iexact=Roles.SALESPERSON.name)
    salesperson_group.user_set.add(salesperson_profile.user)

    customer_profile = ProfileFactory()
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(salesperson_profile)}"
    )
    data = create_application_data(customer_profile)
    data["profile"] = customer_profile.id
    response = api_client.post(
        reverse("application_form:sales-application-list"), data, format="json"
    )
    assert response.status_code == 201
    assert response.data == {"application_uuid": data["application_uuid"]}

    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert str(application.profile.id) == customer_profile.id
