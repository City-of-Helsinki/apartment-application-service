import pytest
from django.utils.translation import gettext_lazy as _

from customer.tests.factories import CustomerFactory
from invoicing.pdf import _get_payer_name_and_address
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_pdf_payer_name_address_correct():
    customer = CustomerFactory(
        primary_profile=ProfileFactory(), secondary_profile=ProfileFactory()
    )
    payer_name_address = _get_payer_name_and_address(customer)

    expected_payer_name_address = (
        f"{customer.primary_profile.full_name} {_('and')} {customer.secondary_profile.full_name}\n\n"  # noqa: E501
        f"{customer.primary_profile.street_address}\n"
        f"{customer.primary_profile.postal_code} {customer.primary_profile.city}"
    )
    assert payer_name_address == expected_payer_name_address
