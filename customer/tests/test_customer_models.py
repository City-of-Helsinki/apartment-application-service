"""
Test cases for customer models.
"""

import pytest
from django.core.exceptions import ValidationError

from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
@pytest.mark.parametrize("has_secondary_profile", (True, False))
def test_customer_model(has_secondary_profile):
    """Test customer model"""

    params = {"secondary_profile": ProfileFactory()} if has_secondary_profile else {}
    customer = CustomerFactory(**params)

    result = Customer.objects.first()
    assert result.id == customer.id
    assert bool(result.secondary_profile) is has_secondary_profile


@pytest.mark.django_db
def test_customer_validation():
    one_profile_customer = CustomerFactory(secondary_profile=None)
    two_profile_customer = CustomerFactory(secondary_profile=ProfileFactory())

    # make sure a profile can be in many customers as long as the secondary profile
    # differs
    CustomerFactory(
        primary_profile=one_profile_customer.primary_profile,
        secondary_profile=ProfileFactory(),
    )
    CustomerFactory(
        primary_profile=two_profile_customer.primary_profile,
        secondary_profile=ProfileFactory(),
    )
    CustomerFactory(
        primary_profile=two_profile_customer.primary_profile,
        secondary_profile=None,
    )

    with pytest.raises(ValidationError):
        # customers with the same primary and no secondary profile are not allowed
        CustomerFactory(
            primary_profile=one_profile_customer.primary_profile, secondary_profile=None
        )

    with pytest.raises(ValidationError):
        # customers with the same primary and secondary profiles are not allowed
        CustomerFactory(
            primary_profile=two_profile_customer.primary_profile,
            secondary_profile=two_profile_customer.secondary_profile,
        )
