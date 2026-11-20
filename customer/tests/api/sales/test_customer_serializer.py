"""
Test cases for the sales CustomerSerializer validators and DB uniqueness.
"""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status

from customer.api.sales.serializers import CustomerSerializer
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory

CUSTOMER_UPDATE_DATA = {
    "additional_information": "",
    "has_children": False,
    "has_hitas_ownership": False,
    "is_age_over_55": False,
    "is_right_of_occupancy_housing_changer": False,
    "last_contact_date": None,
    "right_of_residence": 127,
    "right_of_residence_is_old_batch": False,
    "secondary_profile": None,
}


def _profile_data(profile):
    """
    Return writable sales API data for an existing profile.

            Parameters:
                    profile (Profile): Profile to serialize

            Returns:
                    data (dict): Nested profile payload for CustomerSerializer
    """
    return {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone_number": profile.phone_number,
        "national_identification_number": profile.national_identification_number,
        "street_address": profile.street_address,
        "postal_code": profile.postal_code,
        "city": profile.city,
        "contact_language": profile.contact_language,
        "date_of_birth": profile.date_of_birth.isoformat(),
    }


def test_customer_serializer_has_no_model_level_validators():
    """
    - No UniqueTogetherValidator is auto-generated for the nested profiles.
    """
    assert CustomerSerializer().validators == []


@pytest.mark.django_db
def test_duplicate_sole_primary_profile_customer_raises_integrity_error():
    """
    - DB still rejects a second Customer with the same primary profile
      and no secondary profile.
    - Model.save() validation is bypassed via bulk_create to reach the DB.
    """
    existing = CustomerFactory(secondary_profile=None)
    duplicate = Customer(
        primary_profile=existing.primary_profile,
        secondary_profile=None,
        right_of_residence_is_old_batch=False,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.bulk_create([duplicate])


@pytest.mark.django_db
def test_duplicate_primary_and_secondary_profile_customer_raises_integrity_error():
    """
    - DB still rejects a second Customer with the same primary and secondary
      profile pair.
    """
    existing = CustomerFactory(secondary_profile=ProfileFactory())
    duplicate = Customer(
        primary_profile=existing.primary_profile,
        secondary_profile=existing.secondary_profile,
        right_of_residence_is_old_batch=False,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.bulk_create([duplicate])


@pytest.mark.django_db
def test_customer_with_different_secondary_profile_is_allowed():
    """
    - A primary profile can belong to several customers when the secondary
      profile differs.
    """
    existing = CustomerFactory(secondary_profile=None)

    Customer.objects.bulk_create(
        [
            Customer(
                primary_profile=existing.primary_profile,
                secondary_profile=ProfileFactory(),
                right_of_residence_is_old_batch=False,
            )
        ]
    )

    customers = Customer.objects.filter(primary_profile=existing.primary_profile)
    assert customers.count() == 2


@pytest.mark.django_db
def test_update_customer_removing_secondary_profile_succeeds(
    sales_ui_salesperson_api_client,
):
    """
    - A couple customer is turned into a sole customer via PUT.
    - No other sole customer exists for the primary profile.
    - The update succeeds and the secondary profile is removed.
    """
    customer = CustomerFactory(secondary_profile=ProfileFactory())
    data = {
        **CUSTOMER_UPDATE_DATA,
        "primary_profile": _profile_data(customer.primary_profile),
    }

    response = sales_ui_salesperson_api_client.put(
        reverse("customer:sales-customer-detail", kwargs={"pk": customer.pk}),
        data=data,
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK, response.data
    customer.refresh_from_db()
    assert customer.secondary_profile is None


@pytest.mark.django_db
def test_update_customer_into_duplicate_sole_customer_is_rejected(
    sales_ui_salesperson_api_client,
):
    """
    - A sole customer already exists for the primary profile.
    - A couple customer with the same primary profile drops its secondary
      profile via PUT, which would duplicate the sole customer.
    - The API responds with 400 and an error message instead of a 500.
    - The couple customer keeps its secondary profile.
    """
    sole_customer = CustomerFactory(secondary_profile=None)
    secondary_profile = ProfileFactory()
    couple_customer = CustomerFactory(
        primary_profile=sole_customer.primary_profile,
        secondary_profile=secondary_profile,
    )
    data = {
        **CUSTOMER_UPDATE_DATA,
        "primary_profile": _profile_data(couple_customer.primary_profile),
    }

    response = sales_ui_salesperson_api_client.put(
        reverse("customer:sales-customer-detail", kwargs={"pk": couple_customer.pk}),
        data=data,
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data
    couple_customer.refresh_from_db()
    assert str(couple_customer.secondary_profile_id) == str(secondary_profile.pk)
    assert (
        Customer.objects.filter(
            primary_profile=sole_customer.primary_profile,
            secondary_profile__isnull=True,
        ).count()
        == 1
    )
