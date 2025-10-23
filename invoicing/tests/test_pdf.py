from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory
from invoicing.enums import InstallmentType
from invoicing.tests.factories import ApartmentInstallmentFactory
import pytest
from django.utils.translation import gettext_lazy as _

from customer.tests.factories import CustomerFactory
from invoicing.pdf import (
    _get_payer_name_and_address,
    get_invoice_pdf_data_from_installment,
)
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
@pytest.mark.parametrize("ownership_type", (OwnershipType.HASO, OwnershipType.HITAS))
def test_pdf_payment_recipients_set_correctly(ownership_type):
    apartment = ApartmentDocumentFactory(
        project_ownership_type=ownership_type.value,
        project_payment_recipient="Payment recipient",
        project_payment_recipient_final="Final payment recipient",
    )
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    first_installment_type = InstallmentType.PAYMENT_1
    final_installment_type = InstallmentType.PAYMENT_7

    if ownership_type == OwnershipType.HASO:
        first_installment_type = InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT
        final_installment_type = InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3

    first_installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        value=100_000,
        type=first_installment_type,
    )

    final_installment = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        value=100_000,
        type=final_installment_type,
    )

    first_installment_pdf_data = get_invoice_pdf_data_from_installment(
        first_installment
    )
    final_installment_pdf_data = get_invoice_pdf_data_from_installment(
        final_installment
    )

    assert first_installment_pdf_data.recipient == apartment.project_payment_recipient
    assert (
        final_installment_pdf_data.recipient
        == apartment.project_payment_recipient_final
    )  # noqa: E501

    # assert the final payment still gets the final recipient

    pass


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
