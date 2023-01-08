import pytest
from datetime import date
from unittest.mock import patch

from invoicing.models import ApartmentInstallment, Payment, ProjectInstallmentTemplate
from invoicing.tests.factories import (
    ApartmentInstallmentFactory,
    PaymentFactory, ProjectInstallmentTemplateFactory,
)


@pytest.mark.django_db
def test_project_installment_template_factory_creation():
    ProjectInstallmentTemplateFactory()
    assert ProjectInstallmentTemplate.objects.count() == 1


@pytest.mark.django_db
def test_apartment_installment_factory_creation():
    ApartmentInstallmentFactory()
    assert ApartmentInstallment.objects.count() == 1


@pytest.mark.django_db
def test_apartment_installment_save_invoice_numbers(settings):
    invoice_number_prefix = "123"

    settings.INVOICE_NUMBER_PREFIX = invoice_number_prefix

    for x in range(3):
        expected_invoice_number = invoice_number_prefix + str(x + 1).zfill(6)

        apartment_installment = ApartmentInstallmentFactory()
        apartment_installment.invoice_number = None
        apartment_installment.save()

        assert apartment_installment.invoice_number == expected_invoice_number


@pytest.mark.django_db
def test_apartment_installment_change_invoice_prefix_middle_of_year_and_save_invoices(
    settings,
):
    for x in range(3):
        invoice_number_prefix = str(x + 1).zfill(3)

        settings.INVOICE_NUMBER_PREFIX = invoice_number_prefix

        expected_invoice_number = invoice_number_prefix + "1".zfill(6)

        apartment_installment = ApartmentInstallmentFactory()
        apartment_installment.invoice_number = None
        apartment_installment.save()

        assert apartment_installment.invoice_number == expected_invoice_number


@pytest.mark.django_db
def test_apartment_installment_change_year_and_restart_invoice_numbers(
    settings,
):
    invoice_number_prefix = "123"

    settings.INVOICE_NUMBER_PREFIX = invoice_number_prefix

    for x in range(3):
        with patch("invoicing.models.date") as mock_date:
            mock_date.today.return_value = date(2010 + x, 1, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            expected_invoice_number = invoice_number_prefix + "1".zfill(6)

            apartment_installment = ApartmentInstallmentFactory()
            apartment_installment.invoice_number = None
            apartment_installment.save()

            assert apartment_installment.invoice_number == expected_invoice_number


@pytest.mark.django_db
def test_payment_creation():
    PaymentFactory()
    assert Payment.objects.count() == 1
