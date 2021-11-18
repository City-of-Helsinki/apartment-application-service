"""
Test cases for customer models.
"""
import pytest

from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_customer_model():
    """Test customer model"""

    customer = CustomerFactory(profiles=ProfileFactory.create_batch(2))

    result = Customer.objects.first()
    assert result.id == customer.id
    assert result.profiles.count() == 2
