"""
Test cases for customer api of sales.
"""
import uuid

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import LotteryEvent
from application_form.tests.factories import ApartmentReservationFactory
from customer.api.sales.views import CustomerViewSet
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from customer.tests.utils import assert_customer_list_match_data
from invoicing.tests.factories import ApartmentInstallmentFactory
from users.enums import Roles
from users.models import Profile
from users.tests.factories import ProfileFactory, UserFactory
from users.tests.utils import assert_customer_match_data, assert_profile_match_data


@pytest.mark.django_db
def test_get_customer_api_detail_unauthorized(user_api_client):
    customer = CustomerFactory()

    response = user_api_client.get(
        reverse("customer:sales-customer-detail", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_get_customer_api_detail(sales_ui_salesperson_api_client):
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
        has_hitas_ownership=True,
        has_children=False,
        queue_position=1,
    )
    installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation, value=100
    )

    response = sales_ui_salesperson_api_client.get(
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
            "cancellation_reason": None,
            "changed_by": None,
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
                    "payment_state": {
                        "status": "UNPAID",
                        "is_overdue": False,
                    },
                    "payments": [],
                }
            ],
            "lottery_position": None,
            "project_lottery_completed": False,
            "queue_position": 1,
            "queue_position_before_cancelation": None,
            "priority_number": reservation.application_apartment.priority_number,
            "state": reservation.state.value,
            "offer": None,
            "right_of_residence": reservation.right_of_residence,
            "right_of_residence_is_old_batch": reservation.right_of_residence_is_old_batch,  # noqa: E501
            "has_children": reservation.has_children,
            "has_hitas_ownership": reservation.has_hitas_ownership,
            "is_age_over_55": reservation.is_age_over_55,
            "is_right_of_occupancy_housing_changer": reservation.is_right_of_occupancy_housing_changer,  # noqa: E501
            "submitted_late": reservation.submitted_late,
        }
    ]


@pytest.mark.django_db
def test_customer_detail_state_event_cancellation_reason(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory(
        sales_price=2000,
        debt_free_sales_price=1500,
        right_of_occupancy_payment=300,
    )
    customer = CustomerFactory(secondary_profile=ProfileFactory())
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
    )
    reservation.set_state(
        ApartmentReservationState.CANCELED,
        cancellation_reason=ApartmentReservationCancellationReason.CANCELED,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-detail", args=(customer.pk,)),
        format="json",
    )

    assert (
        response.data["apartment_reservations"][0]["state_change_events"][1][
            "cancellation_reason"
        ]
        == "canceled"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("has_profile", (False, True))
def test_customer_detail_state_event_changed_by(
    sales_ui_salesperson_api_client, has_profile
):
    apartment = ApartmentDocumentFactory(
        sales_price=2000,
        debt_free_sales_price=1500,
        right_of_occupancy_payment=300,
    )
    customer = CustomerFactory(secondary_profile=ProfileFactory())
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
    )
    user = UserFactory()
    Group.objects.get(name__iexact=Roles.DJANGO_SALESPERSON.name).user_set.add(user)
    if has_profile:
        ProfileFactory(user=user)

    reservation.set_state(
        ApartmentReservationState.CANCELED,
        cancellation_reason=ApartmentReservationCancellationReason.CANCELED,
        user=user,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-detail", args=(customer.pk,)),
        format="json",
    )

    assert (
        response.data["apartment_reservations"][0]["state_change_events"][1][
            "changed_by"
        ]
        == {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }
        if not has_profile
        else {
            "id": user.id,
            "first_name": user.profile.first_name,
            "last_name": user.profile.last_name,
            "email": user.profile.email,
        }
    )


@pytest.mark.django_db
def test_get_customer_api_list_without_any_parameters(sales_ui_salesperson_api_client):
    CustomerFactory(secondary_profile=None)
    CustomerFactory(secondary_profile=ProfileFactory())

    expected_data = []

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"), format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == expected_data


@pytest.mark.parametrize("with_secondary_profile", (False, True))
@pytest.mark.django_db
def test_create_customer(sales_ui_salesperson_api_client, with_secondary_profile):
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

    response = sales_ui_salesperson_api_client.post(
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
    sales_ui_salesperson_api_client,
    has_secondary_profile,
    updated_with_secondary_profile,
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
        "right_of_residence_is_old_batch": True,
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

    response = sales_ui_salesperson_api_client.put(
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
def test_get_customer_api_list_with_parameters(sales_ui_salesperson_api_client):
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
    response = sales_ui_salesperson_api_client.get(
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
    response = sales_ui_salesperson_api_client.get(
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
    response = sales_ui_salesperson_api_client.get(
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


@pytest.mark.django_db
def test_customer_reservation_ordering(sales_ui_salesperson_api_client):
    project_uuid = uuid.uuid4()
    apartment_a5 = ApartmentDocumentFactory(
        project_uuid=project_uuid, apartment_number="A5"
    )
    apartment_a10 = ApartmentDocumentFactory(
        project_uuid=project_uuid, apartment_number="A10"
    )
    LotteryEvent.objects.create(apartment_uuid=apartment_a5.uuid)
    LotteryEvent.objects.create(apartment_uuid=apartment_a10.uuid)

    customer = CustomerFactory()

    # these should be returned in reversed order
    reservations = [
        ApartmentReservationFactory(
            apartment_uuid=apartment_a10.uuid,
            customer=customer,
            state=ApartmentReservationState.CANCELED,
            queue_position=None,
            list_position=2,
        ),
        ApartmentReservationFactory(
            apartment_uuid=apartment_a5.uuid,
            customer=customer,
            state=ApartmentReservationState.CANCELED,
            queue_position=None,
            list_position=1,
        ),
        ApartmentReservationFactory(
            apartment_uuid=apartment_a5.uuid,
            customer=customer,
            state=ApartmentReservationState.SUBMITTED,
            queue_position=2,
            list_position=2,
        ),
        ApartmentReservationFactory(
            apartment_uuid=apartment_a10.uuid,
            customer=customer,
            state=ApartmentReservationState.RESERVED,
            queue_position=1,
            list_position=1,
        ),
    ]
    reservation_ids = [r.id for r in reservations]

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-detail", kwargs={"pk": customer.pk}),
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    returned_ids = [r["id"] for r in response.data["apartment_reservations"]]

    assert returned_ids == list(reversed(reservation_ids))
