"""
Test cases for customer api of sales.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


@pytest.mark.django_db
def test_get_customer_api_detail(api_client):
    customer = CustomerFactory(secondary_profile=ProfileFactory())

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("customer:sales-customer-detail", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data
    assert response.data.get("id") == customer.pk
    assert response.data["primary_profile"]
    assert response.data["primary_profile"].get("id") == customer.primary_profile.id
    assert response.data["primary_profile"]["national_identification_number"]
    assert response.data["secondary_profile"]
    assert response.data["secondary_profile"].get("id") == customer.secondary_profile.id
    assert response.data["secondary_profile"]["national_identification_number"]


@pytest.mark.django_db
def test_get_customer_api_list(api_client):
    CustomerFactory(secondary_profile=None)
    CustomerFactory(secondary_profile=ProfileFactory())

    expected_data = []
    for customer in Customer.objects.all().order_by(
        "primary_profile__last_name", "primary_profile__first_name"
    ):
        item = {
            "id": customer.id,
            "primary_first_name": customer.primary_profile.first_name,
            "primary_last_name": customer.primary_profile.last_name,
            "primary_email": customer.primary_profile.email,
            "primary_phone_number": customer.primary_profile.phone_number,
            "secondary_first_name": customer.secondary_profile.first_name
            if customer.secondary_profile
            else None,
            "secondary_last_name": customer.secondary_profile.last_name
            if customer.secondary_profile
            else None,
        }
        expected_data.append(item)

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(reverse("customer:sales-customer-list"), format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == expected_data
