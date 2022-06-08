"""
Test cases for customer api of sales.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory
from customer.api.sales.views import CustomerViewSet
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from customer.tests.utils import assert_customer_list_match_data
from invoicing.tests.factories import ApartmentInstallmentFactory
from users.models import Profile
from users.tests.factories import ProfileFactory
from users.tests.utils import (
    _create_token,
    assert_customer_match_data,
    assert_profile_match_data,
)


@pytest.mark.django_db
def test_get_customer_api_detail(salesperson_api_client):
    apartment = ApartmentDocumentFactory(
        sales_price=2000,
        debt_free_sales_price=1500,
        right_of_occupancy_payment=300,
    )
    customer = CustomerFactory(secondary_profile=ProfileFactory())
    reservation = ApartmentReservationFactory(
        application_apartment__application__customer=customer,
        application_apartment__apartment_uuid=apartment.uuid,
        customer=customer,
        apartment_uuid=apartment.uuid,
    )
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation, value=100
    )

    profile = ProfileFactory()
    salesperson_api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}"
    )
    response = salesperson_api_client.get(
        reverse("customer:sales-customer-detail", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data
    assert response.data.get("id") == customer.pk
    assert "primary_profile" in response.data
    assert_profile_match_data(
        customer.primary_profile, response.data["primary_profile"]
    )
    assert "secondary_profile" in response.data
    assert_profile_match_data(
        customer.secondary_profile, response.data["secondary_profile"]
    )
    state_change_events = response.data["apartment_reservations"][0].pop(
        "state_change_events"
    )
    assert state_change_events[0]["timestamp"] is not None
    state_change_events[0].pop("timestamp")
    assert state_change_events == [
        {
            "comment": reservation.state_change_events.first().comment,
            "state": reservation.state_change_events.first().state.value,
        }
    ]
    assert response.data["apartment_reservations"] == [
        {
            "id": reservation.id,
            "project_uuid": apartment.project_uuid,
            "project_housing_company": apartment.project_housing_company,
            "project_ownership_type": apartment.project_ownership_type,
            "project_street_address": apartment.project_street_address,
            "project_district": apartment.project_district,
            "apartment_uuid": apartment.uuid,
            "apartment_number": apartment.apartment_number,
            "apartment_structure": apartment.apartment_structure,
            "apartment_living_area": apartment.living_area,
            "apartment_sales_price": 2000,
            "apartment_debt_free_sales_price": 1500,
            "apartment_right_of_occupancy_payment": 300,
            "apartment_installments": [
                {
                    "type": installment.type.value,
                    "amount": 10000,
                    "account_number": installment.account_number,
                    "due_date": str(installment.due_date)
                    if installment.due_date
                    else None,
                    "reference_number": installment.reference_number,
                    "added_to_be_sent_to_sap_at": installment.added_to_be_sent_to_sap_at,  # noqa: E501
                }
            ],
            "lottery_position": None,
            "project_lottery_completed": False,
            "queue_position": None,
            "priority_number": reservation.application_apartment.priority_number,
            "state": reservation.state.value,
            "offer": None,
        }
    ]


@pytest.mark.django_db
def test_get_customer_api_list_without_any_parameters(salesperson_api_client):
    CustomerFactory(secondary_profile=None)
    CustomerFactory(secondary_profile=ProfileFactory())

    expected_data = []

    response = salesperson_api_client.get(
        reverse("customer:sales-customer-list"), format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == expected_data


@pytest.mark.parametrize("with_secondary_profile", (False, True))
@pytest.mark.django_db
def test_create_customer(salesperson_api_client, with_secondary_profile):
    data = {
        "additional_information": "",
        "has_children": False,
        "has_hitas_ownership": False,
        "is_age_over_55": False,
        "is_right_of_occupancy_housing_changer": False,
        "last_contact_date": None,
        "primary_profile": {
            "first_name": "Matti",
            "last_name": "Mainio",
            "email": "matti@example.com",
            "phone_number": "777-123123",
            "national_identification_number": "070780-111A",
            "street_address": "Jokutie 5 D",
            "postal_code": "88890",
            "city": "Helsinki",
            "contact_language": "fi",
            "date_of_birth": "1980-07-07",
        },
        "right_of_residence": 127,
    }

    if with_secondary_profile:
        data["secondary_profile"] = {
            "first_name": "Jussi",
            "last_name": "Juonio",
            "email": "jussi@example.com",
            "phone_number": "777-321321",
            "national_identification_number": "080890-222B",
            "street_address": "Jokutie 5 D",
            "postal_code": "99990",
            "city": "Turku",
            "contact_language": "sv",
            "date_of_birth": "1990-08-08",
        }
    else:
        data["secondary_profile"] = None

    response = salesperson_api_client.post(
        reverse("customer:sales-customer-list"), data=data, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED, response.data

    assert Customer.objects.count() == 1
    assert Profile.objects.count() == 2 if with_secondary_profile else 1
    customer = Customer.objects.get(pk=response.data["id"])
    assert_customer_match_data(customer, data)


@pytest.mark.parametrize("has_secondary_profile", (False, True))
@pytest.mark.parametrize("updated_with_secondary_profile", (False, True))
@pytest.mark.django_db
def test_update_customer(
    salesperson_api_client, has_secondary_profile, updated_with_secondary_profile
):
    customer = CustomerFactory(
        primary_profile=ProfileFactory(),
        secondary_profile=ProfileFactory() if has_secondary_profile else None,
    )

    data = {
        "additional_information": "moar info",
        "has_children": True,
        "has_hitas_ownership": True,
        "is_age_over_55": True,
        "is_right_of_occupancy_housing_changer": False,
        "last_contact_date": "2020-01-01",
        "primary_profile": {
            "first_name": "Matti",
            "last_name": "Mainio",
            "email": "matti@example.com",
            "phone_number": "777-123123",
            "national_identification_number": "070780-111A",
            "street_address": "Jokutie 5 D",
            "postal_code": "88890",
            "city": "Helsinki",
            "contact_language": "fi",
            "date_of_birth": "1980-07-07",
        },
        "right_of_residence": 127,
    }

    if updated_with_secondary_profile:
        data["secondary_profile"] = {
            "first_name": "Jussi",
            "last_name": "Juonio",
            "email": "jussi@example.com",
            "phone_number": "777-321321",
            "national_identification_number": "080890-222B",
            "street_address": "Jokutie 5 D",
            "postal_code": "99990",
            "city": "Turku",
            "contact_language": "sv",
            "date_of_birth": "1990-08-08",
        }
    else:
        data["secondary_profile"] = None

    response = salesperson_api_client.put(
        reverse("customer:sales-customer-detail", kwargs={"pk": customer.pk}),
        data=data,
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    assert Customer.objects.count() == 1

    if not has_secondary_profile and not updated_with_secondary_profile:
        expected_profile_count = 1
    else:
        expected_profile_count = 2
    assert Profile.objects.count() == expected_profile_count

    customer.refresh_from_db()
    assert_customer_match_data(customer, data)


@pytest.mark.django_db
def test_get_customer_api_list_with_parameters(salesperson_api_client):
    customers = {}
    customer = CustomerFactory(
        primary_profile__first_name="John",
        primary_profile__last_name="Doe",
        secondary_profile=None,
    )
    customers[customer.id] = customer

    customer_with_secondary = CustomerFactory(
        primary_profile__first_name="Jane",
        primary_profile__last_name="Doe",
        secondary_profile=ProfileFactory(first_name="John", last_name="Doe"),
    )
    customers[customer_with_secondary.id] = customer_with_secondary

    # Search value is less than min length
    response = salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={
            "last_name": customer.primary_profile.last_name[
                : CustomerViewSet.SEARCH_VALUE_MIN_LENGTH - 1
            ]
        },
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data == []

    # Search value's minimum length has reached
    response = salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={
            "last_name": customer.primary_profile.last_name[
                : CustomerViewSet.SEARCH_VALUE_MIN_LENGTH
            ]
        },
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data
    assert len(response.data) == 2
    for item in response.data:
        assert_customer_list_match_data(customers[item["id"]], item)

    # Search value with two params
    response = salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={
            "first_name": customer_with_secondary.primary_profile.first_name[
                : CustomerViewSet.SEARCH_VALUE_MIN_LENGTH
            ],
            "last_name": customer_with_secondary.primary_profile.last_name[
                : CustomerViewSet.SEARCH_VALUE_MIN_LENGTH
            ],
        },
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data
    assert len(response.data) == 1
    for item in response.data:
        assert_customer_list_match_data(customers[item["id"]], item)
