from datetime import date
from decimal import Decimal

import pytest

from invoicing.models import PaymentBatch
from invoicing.sap.fetch import (
    process_payment_data,
    SapPaymentDataAlreadyProcessedError,
    SapPaymentDataParsingError,
)
from invoicing.tests.factories import ApartmentInstallmentFactory, PaymentFactory

VALID_TEST_PAYMENT_DATA = """022121917199          12800     0000000000000000000000000000000000000000000000000000000000
30000001070015222121822121863224                               SAP BTestaaj1 00006658101  
30000001070015222121822121863224                               SAP ATestaaj1 00006658100  
30000001011589724051024051063224                               Halotainen V1 00062905000  
900000200001331620000000000000000000000000000000000000000000000000000000000000000000000000
"""  # noqa: E501, W291

INVALID_TEST_PAYMENT_DATA = """022121917199          12800     0000000000000000000000000000000000000000000000000000000000
300000
300000010700152221218221218730000077                           SAP ATestaaj1 00006658100  
300000010700152221218221218730000078                           SAP BTestaaj1 00006658101  
900000200001331620000000000000000000000000000000000000000000000000000000000000000000000000
"""  # noqa: E501, W291

EXPECTED_ERROR_MESSAGE = """Parsing errors:
2: Incorrect line length 6"""  # noqa: E501, W291


@pytest.mark.parametrize("has_filename", (True, False))
@pytest.mark.django_db
def test_read_payments_data(has_filename):
    installment = ApartmentInstallmentFactory(invoice_number=63224)
    another_installment = ApartmentInstallmentFactory()

    if has_filename:
        num_of_payments = process_payment_data(
            VALID_TEST_PAYMENT_DATA, filename="test_payments_123.txt"
        )
    else:
        num_of_payments = process_payment_data(VALID_TEST_PAYMENT_DATA)

    assert installment.payments.count() == 3
    payment_1, payment_2, payment_3 = installment.payments.all()
    assert payment_1.payment_date == date(2022, 12, 18)
    assert payment_1.amount == Decimal("6658.10")
    assert payment_2.payment_date == date(2022, 12, 18)
    assert payment_2.amount == Decimal("6658.10")
    assert payment_3.payment_date == date(2024, 5, 10)
    assert payment_3.amount == Decimal("62905.00")
    assert another_installment.payments.count() == 0
    assert num_of_payments == 3

    if has_filename:
        assert PaymentBatch.objects.count() == 1
        batch = PaymentBatch.objects.first()
        assert batch.filename == "test_payments_123.txt"
        assert list(batch.payments.all()) == [payment_1, payment_2, payment_3]
    else:
        assert PaymentBatch.objects.count() == 0


@pytest.mark.django_db
def test_read_payments_data_parsing_errors():
    installment = ApartmentInstallmentFactory(invoice_number=730000078)
    payment = PaymentFactory(apartment_installment=installment)

    with pytest.raises(SapPaymentDataParsingError) as excinfo:
        process_payment_data(INVALID_TEST_PAYMENT_DATA)

    assert str(excinfo.value) == EXPECTED_ERROR_MESSAGE
    assert list(installment.payments.all()) == [payment]


@pytest.mark.django_db
def test_read_payments_data_file_already_processed_error():
    test_payment_data = VALID_TEST_PAYMENT_DATA
    ApartmentInstallmentFactory(invoice_number=730000077)
    process_payment_data(test_payment_data, filename="test_payments_123.txt")

    with pytest.raises(SapPaymentDataAlreadyProcessedError):
        process_payment_data(test_payment_data, filename="test_payments_123.txt")
