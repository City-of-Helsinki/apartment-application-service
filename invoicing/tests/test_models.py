import pytest
from datetime import date
from freezegun import freeze_time
from unittest.mock import patch

from invoicing.enums import PaymentStatus
from invoicing.models import ApartmentInstallment, Payment, ProjectInstallmentTemplate
from invoicing.tests.factories import (
    ApartmentInstallmentFactory,
    PaymentFactory,
    ProjectInstallmentTemplateFactory,
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_amounts, expected_status",
    (
        ([], PaymentStatus.UNPAID),
        ([50], PaymentStatus.UNDERPAID),
        ([60, 33], PaymentStatus.UNDERPAID),
        ([100], PaymentStatus.PAID),
        ([60, 40], PaymentStatus.PAID),
        ([101], PaymentStatus.OVERPAID),
        ([99, 2], PaymentStatus.OVERPAID),
    ),
)
def test_apartment_installment_payment_status(payment_amounts, expected_status):
    installment = ApartmentInstallmentFactory(value=100)
    PaymentFactory(amount=200)  # just some other payment that should not affect

    for payment_amount in payment_amounts:
        PaymentFactory(apartment_installment=installment, amount=payment_amount)

    assert installment.payment_status == expected_status


@pytest.mark.django_db
def test_apartment_installment_is_overdue():
    date_in_past = date(2020, 2, 1)
    current_date = date(2020, 2, 2)

    unpaid_no_due_date = ApartmentInstallmentFactory(value=100, due_date=None)

    unpaid_not_overdue = ApartmentInstallmentFactory(value=100, due_date=current_date)

    unpaid_overdue = ApartmentInstallmentFactory(value=100, due_date=date_in_past)

    paid_in_time = ApartmentInstallmentFactory(value=100, due_date=date_in_past)
    PaymentFactory(
        apartment_installment=paid_in_time, amount=100, payment_date=date_in_past
    )

    paid_no_due_date = ApartmentInstallmentFactory(value=100, due_date=None)
    PaymentFactory(
        apartment_installment=paid_no_due_date, amount=100, payment_date=current_date
    )

    partially_paid_in_time = ApartmentInstallmentFactory(
        value=100, due_date=date_in_past
    )
    PaymentFactory(
        apartment_installment=partially_paid_in_time,
        amount=90,
        payment_date=date_in_past,
    )
    PaymentFactory(
        apartment_installment=partially_paid_in_time,
        amount=10,
        payment_date=current_date,
    )

    with freeze_time(current_date):
        assert unpaid_no_due_date.is_overdue is False
        assert unpaid_not_overdue.is_overdue is False
        assert unpaid_overdue.is_overdue is True
        assert paid_in_time.is_overdue is False
        assert paid_no_due_date.is_overdue is False
        assert partially_paid_in_time.is_overdue is True
