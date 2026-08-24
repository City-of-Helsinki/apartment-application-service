"""
Test cases for customer api of sales.
"""

import uuid
from unittest.mock import patch

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
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicantFactory,
    ApplicationFactory,
)
from customer.api.sales.views import CustomerViewSet
from customer.models import Customer, CustomerComment
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
    ApartmentReservationFactory(
        application_apartment__application__customer=customer,
        application_apartment__apartment_uuid=apartment.uuid,
        customer=customer,
        apartment_uuid=apartment.uuid,
        has_hitas_ownership=True,
        has_children=False,
        queue_position=1,
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
    # Reservations are now served by a dedicated paginated sub-resource.
    assert "apartment_reservations" not in response.data


@pytest.mark.django_db
def test_get_customer_api_detail_resolves_profile_fields_from_latest_applicant(
    sales_ui_salesperson_api_client,
):
    """
    - Customer detail resolves missing and dash-like profile fields.
    - Latest primary applicant is used as fallback source.
    """
    customer = CustomerFactory(
        primary_profile__email="-",
        primary_profile__phone_number="",
        primary_profile__street_address="-",
        primary_profile__postal_code=" ",
        primary_profile__city="-",
    )

    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="ramona2@test.tst",
        phone_number="0100200",
        street_address="Kekekatu 22",
        postal_code="00200",
        city="Helsinki",
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-detail", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    primary = response.data["primary_profile"]
    assert primary["email"] == "ramona2@test.tst"
    assert primary["phone_number"] == "0100200"
    assert primary["street_address"] == "Kekekatu 22"
    assert primary["postal_code"] == "00200"
    assert primary["city"] == "Helsinki"


@pytest.mark.django_db
def test_customer_detail_does_not_fetch_apartments(sales_ui_salesperson_api_client):
    """
    The customer detail endpoint must not perform per-reservation apartment
    lookups; those are now served by the paginated sub-resource.
    """
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    for position in range(1, 4):
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            customer=customer,
            list_position=position,
        )

    with patch("customer.api.sales.serializers.get_apartment") as mocked_get_apartment:
        response = sales_ui_salesperson_api_client.get(
            reverse("customer:sales-customer-detail", args=(customer.pk,)),
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert mocked_get_apartment.call_count == 0


@pytest.mark.django_db
def test_customer_apartment_reservations_unauthorized(user_api_client):
    customer = CustomerFactory()

    response = user_api_client.get(
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_customer_apartment_reservations_not_found(sales_ui_salesperson_api_client):
    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-apartment-reservations", args=(99999,)),
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_customer_apartment_reservations_returns_serialized_row(
    sales_ui_salesperson_api_client,
):
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
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data.keys()) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 1
    assert response.data["next"] is None
    assert response.data["previous"] is None

    results = response.data["results"]
    assert len(results) == 1

    state_change_events = results[0].pop("state_change_events")
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

    assert results == [
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
                    "due_date": (
                        str(installment.due_date) if installment.due_date else None
                    ),
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
def test_customer_apartment_reservations_state_event_cancellation_reason(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
    )
    reservation.set_state(
        ApartmentReservationState.CANCELED,
        cancellation_reason=ApartmentReservationCancellationReason.CANCELED,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert (
        response.data["results"][0]["state_change_events"][1]["cancellation_reason"]
        == "canceled"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("has_profile", (False, True))
def test_customer_apartment_reservations_state_event_changed_by(
    sales_ui_salesperson_api_client, has_profile
):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
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
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert (
        response.data["results"][0]["state_change_events"][1]["changed_by"]
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
def test_customer_apartment_reservations_pagination_envelope(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    for position in range(1, 8):
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            customer=customer,
            list_position=position,
        )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,)),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 7
    # Default page size is 5.
    assert len(response.data["results"]) == 5
    assert response.data["previous"] is None
    assert response.data["next"] is not None

    response_page_two = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,))
        + "?page=2",
        format="json",
    )

    assert response_page_two.status_code == status.HTTP_200_OK
    assert response_page_two.data["count"] == 7
    assert len(response_page_two.data["results"]) == 2
    assert response_page_two.data["next"] is None


@pytest.mark.django_db
def test_customer_apartment_reservations_respects_page_size_query(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    for position in range(1, 13):
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            customer=customer,
            list_position=position,
        )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-apartment-reservations", args=(customer.pk,))
        + "?page_size=3",
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 3


@pytest.mark.django_db
def test_customer_apartment_reservations_only_fetches_page_apartments(
    sales_ui_salesperson_api_client,
):
    """
    Serializing one page must call ``get_apartment`` only for distinct apartment
    UUIDs on the current page (not for the full reservation count), and never
    for rows on other pages.
    """
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    for position in range(1, 13):
        ApartmentReservationFactory(
            apartment_uuid=apartment.uuid,
            customer=customer,
            list_position=position,
        )

    with patch(
        "apartment.elastic.queries.get_apartment",
        return_value=apartment,
    ) as mocked_get_apartment:
        response = sales_ui_salesperson_api_client.get(
            reverse(
                "customer:sales-customer-apartment-reservations",
                args=(customer.pk,),
            )
            + "?page_size=3",
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 3
    assert mocked_get_apartment.call_count == 1


@pytest.mark.django_db
def test_customer_apartment_reservations_one_get_apartment_per_distinct_uuid(
    sales_ui_salesperson_api_client,
):
    """Three different apartments on one page require three ``get_apartment`` calls."""
    from apartment.elastic import queries

    customer = CustomerFactory()
    apartments = [ApartmentDocumentFactory() for _ in range(3)]
    for i, apt in enumerate(apartments, start=1):
        ApartmentReservationFactory(
            apartment_uuid=apt.uuid,
            customer=customer,
            list_position=i,
        )

    with patch.object(
        queries,
        "get_apartment",
        wraps=queries.get_apartment,
    ) as wrapped_get_apartment:
        response = sales_ui_salesperson_api_client.get(
            reverse(
                "customer:sales-customer-apartment-reservations",
                args=(customer.pk,),
            )
            + "?page_size=5",
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 3
    assert wrapped_get_apartment.call_count == 3


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
def test_customer_apartment_reservations_ordering(sales_ui_salesperson_api_client):
    """
    The paginated sub-resource orders reservations DB-side by:
      1. non-canceled first (canceled last)
      2. queue_position ascending, nulls last
      3. id ascending
    """
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

    canceled_first = ApartmentReservationFactory(
        apartment_uuid=apartment_a10.uuid,
        customer=customer,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
        list_position=2,
    )
    canceled_second = ApartmentReservationFactory(
        apartment_uuid=apartment_a5.uuid,
        customer=customer,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
        list_position=1,
    )
    submitted_q2 = ApartmentReservationFactory(
        apartment_uuid=apartment_a5.uuid,
        customer=customer,
        state=ApartmentReservationState.SUBMITTED,
        queue_position=2,
        list_position=2,
    )
    reserved_q1 = ApartmentReservationFactory(
        apartment_uuid=apartment_a10.uuid,
        customer=customer,
        state=ApartmentReservationState.RESERVED,
        queue_position=1,
        list_position=1,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "customer:sales-customer-apartment-reservations",
            kwargs={"pk": customer.pk},
        ),
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    returned_ids = [r["id"] for r in response.data["results"]]

    assert returned_ids == [
        reserved_q1.id,
        submitted_q2.id,
        canceled_first.id,
        canceled_second.id,
    ]


@pytest.mark.django_db
def test_get_customer_api_list_search_by_hetu_primary_profile(
    sales_ui_salesperson_api_client,
):
    """
    Search by hetu (national_identification_number) returns the customer whose
    primary profile hetu matches exactly.

    - Creates two customers with distinct hetu values on their primary profiles
    - Searches for the hetu of the first customer
    - Expects exactly one result matching that customer
    """
    hetu = "070780-111A"
    target_customer = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=hetu),
        secondary_profile=None,
    )
    CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number="080890-222B"),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"hetu": hetu},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == target_customer.id


@pytest.mark.django_db
def test_get_customer_api_list_search_by_hetu_secondary_profile(
    sales_ui_salesperson_api_client,
):
    """
    Search by hetu returns the customer whose secondary profile hetu matches.

    - Creates a customer whose secondary profile has a known hetu
    - Creates another customer that should not be returned
    - Expects exactly one result matching the customer with that secondary profile hetu
    """
    hetu = "080890-222B"
    target_customer = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number="070780-111A"),
        secondary_profile=ProfileFactory(national_identification_number=hetu),
    )
    CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number="010170-333C"),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"hetu": hetu},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == target_customer.id


@pytest.mark.django_db
def test_get_customer_api_list_search_by_hetu_no_match(
    sales_ui_salesperson_api_client,
):
    """
    Search by hetu with no matching customer returns an empty list.

    - Creates a customer with a different hetu
    - Searches for a hetu that does not exist in the database
    - Expects an empty list
    """
    CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number="070780-111A"),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"hetu": "010199-999X"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.django_db
def test_get_customer_api_list_search_by_date_of_birth_primary_profile(
    sales_ui_salesperson_api_client,
):
    """
    Search by date_of_birth (Finnish format d.m.Y) returns the customer whose
    primary profile date of birth matches exactly.

    - Creates two customers with distinct dates of birth on their primary profiles
    - Searches using the Finnish date format for the first customer
    - Expects exactly one result matching that customer
    """
    import datetime

    dob = datetime.date(1978, 9, 3)
    target_customer = CustomerFactory(
        primary_profile=ProfileFactory(date_of_birth=dob),
        secondary_profile=None,
    )
    CustomerFactory(
        primary_profile=ProfileFactory(date_of_birth=datetime.date(1990, 1, 15)),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"date_of_birth": "3.9.1978"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == target_customer.id


@pytest.mark.django_db
def test_get_customer_api_list_search_by_date_of_birth_secondary_profile(
    sales_ui_salesperson_api_client,
):
    """
    Search by date_of_birth returns the customer whose secondary profile date of
    birth matches exactly.

    - Creates a customer whose secondary profile has a known date of birth
    - Creates another customer that should not be returned
    - Expects exactly one result matching the customer with that secondary profile dob
    """
    import datetime

    dob = datetime.date(1985, 12, 31)
    target_customer = CustomerFactory(
        primary_profile=ProfileFactory(date_of_birth=datetime.date(1980, 7, 7)),
        secondary_profile=ProfileFactory(date_of_birth=dob),
    )
    CustomerFactory(
        primary_profile=ProfileFactory(date_of_birth=datetime.date(1975, 3, 20)),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"date_of_birth": "31.12.1985"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == target_customer.id


@pytest.mark.django_db
def test_get_customer_api_list_search_by_date_of_birth_no_match(
    sales_ui_salesperson_api_client,
):
    """
    Search by date_of_birth with no matching customer returns an empty list.

    - Creates a customer with a different date of birth
    - Searches for a date that does not exist in the database
    - Expects an empty list
    """
    import datetime

    CustomerFactory(
        primary_profile=ProfileFactory(date_of_birth=datetime.date(1980, 7, 7)),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"date_of_birth": "1.1.2000"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.django_db
def test_get_customer_api_list_search_by_date_of_birth_invalid_format(
    sales_ui_salesperson_api_client,
):
    """
    Search by date_of_birth with an invalid date string returns an empty list
    instead of raising an exception.

    - Sends a malformed date string
    - Expects an empty list and HTTP 200
    """
    CustomerFactory(secondary_profile=None)

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"date_of_birth": "not-a-date"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.django_db
def test_get_customer_api_list_search_by_hetu_alone_bypasses_min_length_check(
    sales_ui_salesperson_api_client,
):
    """
    Providing only hetu (without first_name, last_name, phone_number or email)
    is sufficient to trigger a search and does not return an empty list due to
    the minimum-length guard applied to other search fields.

    - Creates one customer with a known hetu
    - Searches using only the hetu parameter
    - Expects one result (not an empty list due to min-length guard)
    """
    hetu = "070780-111A"
    target_customer = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=hetu),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"hetu": hetu},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == target_customer.id


@pytest.mark.django_db
def test_get_customer_api_list_deduplicates_safe_solo_customers_by_hetu(
    sales_ui_salesperson_api_client,
):
    """
    Safe-solo duplicates are represented as one row in sales customer list.

    - Two customers have different primary profiles but the same hetu.
    - Both are solo customers (secondary profile is null).
    - Query by shared email returns a single deduplicated row.
    """
    shared_hetu = "311299A1234"
    shared_email = "solo_dedupe@example.com"
    customer_1 = CustomerFactory(
        primary_profile=ProfileFactory(
            first_name="Test",
            last_name="Solo",
            email=shared_email,
            national_identification_number=shared_hetu,
        ),
        secondary_profile=None,
    )
    customer_2 = CustomerFactory(
        primary_profile=ProfileFactory(
            first_name="Test",
            last_name="Solo",
            email=shared_email,
            national_identification_number=shared_hetu,
        ),
        secondary_profile=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"email": shared_email},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == min(customer_1.id, customer_2.id)


@pytest.mark.django_db
def test_customer_apartment_reservations_aggregates_safe_solo_group(
    sales_ui_salesperson_api_client,
):
    """
    Apartment reservations endpoint aggregates rows from safe-solo duplicates.

    - Two solo customers share the same hetu.
    - Reservations exist under both customer IDs.
    - Sub-resource returns reservations from both customers.
    """
    shared_hetu = "311299A1234"
    customer_1 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=shared_hetu),
        secondary_profile=None,
    )
    customer_2 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=shared_hetu),
        secondary_profile=None,
    )

    apartment_1 = ApartmentDocumentFactory()
    apartment_2 = ApartmentDocumentFactory()

    reservation_1 = ApartmentReservationFactory(
        customer=customer_1,
        apartment_uuid=apartment_1.uuid,
        application_apartment__apartment_uuid=apartment_1.uuid,
    )
    reservation_2 = ApartmentReservationFactory(
        customer=customer_2,
        apartment_uuid=apartment_2.uuid,
        application_apartment__apartment_uuid=apartment_2.uuid,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "customer:sales-customer-apartment-reservations",
            args=(customer_1.pk,),
        ),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    returned_ids = {item["id"] for item in response.data["results"]}
    assert returned_ids == {reservation_1.id, reservation_2.id}


@pytest.mark.django_db
def test_customer_comments_aggregates_safe_solo_group(
    sales_ui_salesperson_api_client,
):
    """
    Customer comments endpoint lists comments across safe-solo duplicates.

    - Two solo customers share the same hetu.
    - Both customers have comments.
    - Nested comments endpoint returns the aggregated set.
    """
    shared_hetu = "311299A1234"
    customer_1 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=shared_hetu),
        secondary_profile=None,
    )
    customer_2 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=shared_hetu),
        secondary_profile=None,
    )
    comment_1 = CustomerComment.objects.create(customer=customer_1, content="one")
    comment_2 = CustomerComment.objects.create(customer=customer_2, content="two")

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:customer-comments", kwargs={"customer_pk": customer_1.pk}),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {item["id"] for item in response.data}
    assert returned_ids == {comment_1.id, comment_2.id}


@pytest.mark.django_db
def test_get_customer_api_list_deduplicates_strict_safe_pair_by_hetu(
    sales_ui_salesperson_api_client,
):
    """
    Strict safe-pair duplicates are represented as one row in sales list.

    - Two customers share the same pair hetu values (A+B).
    - Neither A nor B appears with other partners or alone.
    - Query by one pair hetu returns a single deduplicated row.
    """
    hetu_a = "150190A111K"
    hetu_b = "200292A222L"

    customer_1 = CustomerFactory(
        primary_profile=ProfileFactory(
            first_name="Pair",
            last_name="One",
            email="pair_primary@example.com",
            national_identification_number=hetu_a,
        ),
        secondary_profile=ProfileFactory(
            first_name="Pair",
            last_name="Two",
            email="pair_secondary@example.com",
            national_identification_number=hetu_b,
        ),
    )
    customer_2 = CustomerFactory(
        primary_profile=ProfileFactory(
            first_name="Pair",
            last_name="One",
            email="pair_primary@example.com",
            national_identification_number=hetu_a,
        ),
        secondary_profile=ProfileFactory(
            first_name="Pair",
            last_name="Two",
            email="pair_secondary@example.com",
            national_identification_number=hetu_b,
        ),
    )

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:sales-customer-list"),
        data={"hetu": hetu_a},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == min(customer_1.id, customer_2.id)


@pytest.mark.django_db
def test_customer_apartment_reservations_aggregates_strict_safe_pair_group(
    sales_ui_salesperson_api_client,
):
    """
    Apartment reservations endpoint aggregates rows from strict safe-pair duplicates.

    - Two customers share the same pair hetu values (A+B).
    - Reservations exist under both customer IDs.
    - Sub-resource returns reservations from both customers.
    """
    hetu_a = "150190A111K"
    hetu_b = "200292A222L"
    customer_1 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=hetu_a),
        secondary_profile=ProfileFactory(national_identification_number=hetu_b),
    )
    customer_2 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=hetu_a),
        secondary_profile=ProfileFactory(national_identification_number=hetu_b),
    )

    apartment_1 = ApartmentDocumentFactory()
    apartment_2 = ApartmentDocumentFactory()

    reservation_1 = ApartmentReservationFactory(
        customer=customer_1,
        apartment_uuid=apartment_1.uuid,
        application_apartment__apartment_uuid=apartment_1.uuid,
    )
    reservation_2 = ApartmentReservationFactory(
        customer=customer_2,
        apartment_uuid=apartment_2.uuid,
        application_apartment__apartment_uuid=apartment_2.uuid,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "customer:sales-customer-apartment-reservations",
            args=(customer_1.pk,),
        ),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    returned_ids = {item["id"] for item in response.data["results"]}
    assert returned_ids == {reservation_1.id, reservation_2.id}


@pytest.mark.django_db
def test_customer_comments_aggregates_strict_safe_pair_group(
    sales_ui_salesperson_api_client,
):
    """
    Customer comments endpoint lists comments across strict safe-pair duplicates.

    - Two customers share the same pair hetu values (A+B).
    - Both customers have comments.
    - Nested comments endpoint returns the aggregated set.
    """
    hetu_a = "150190A111K"
    hetu_b = "200292A222L"
    customer_1 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=hetu_a),
        secondary_profile=ProfileFactory(national_identification_number=hetu_b),
    )
    customer_2 = CustomerFactory(
        primary_profile=ProfileFactory(national_identification_number=hetu_a),
        secondary_profile=ProfileFactory(national_identification_number=hetu_b),
    )
    comment_1 = CustomerComment.objects.create(customer=customer_1, content="one")
    comment_2 = CustomerComment.objects.create(customer=customer_2, content="two")

    response = sales_ui_salesperson_api_client.get(
        reverse("customer:customer-comments", kwargs={"customer_pk": customer_1.pk}),
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {item["id"] for item in response.data}
    assert returned_ids == {comment_1.id, comment_2.id}
