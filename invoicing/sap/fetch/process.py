from datetime import datetime
from decimal import Decimal
from logging import getLogger
from typing import Optional

from django.db import IntegrityError, transaction

from invoicing.models import ApartmentInstallment, Payment, PaymentBatch

logger = getLogger(__name__)

EVENT_RECORD_ID = "3"  # tapahtumatietue


class SapPaymentDataAlreadyProcessedError(Exception):
    pass


class SapPaymentDataParsingError(Exception):
    pass


class LineParser:
    def __init__(self, line: str):
        assert len(line) == 90, f"Incorrect line length {len(line)}"
        self.line = line

    def get_value_from_line(self, index: int, length: int) -> str:
        return self.line[index : index + length].strip()  # noqa: E203

    def get_payment_date(self) -> datetime.date:
        return datetime.strptime(self.get_value_from_line(15, 6), "%d%m%y").date()

    def get_amount(self) -> Decimal:
        return Decimal(int(self.get_value_from_line(79, 10)) / Decimal("100")).quantize(
            Decimal(".01")
        )

    def get_invoice_number(self) -> int:
        return int(self.get_value_from_line(27, 9))


@transaction.atomic
def process_payment_data(  # noqa: C901
    payment_data: str, filename: Optional[str] = None
) -> int:
    logger.debug(
        f"Processing payment data. Filename: {filename} Data: \n{payment_data}\n"
    )

    if filename:
        try:
            payment_batch = PaymentBatch.objects.create(filename=filename)
        except IntegrityError:
            raise SapPaymentDataAlreadyProcessedError(
                f'Payment file "{filename}" has been processed already.'
            )
    else:
        payment_batch = None

    errors = []
    num_of_payments = 0
    for line_number, line in enumerate(payment_data.splitlines(), 1):
        # Other than event records are ignored at least for now
        if line[0] != EVENT_RECORD_ID:
            continue

        try:
            parser = LineParser(line)
            invoice_number = parser.get_invoice_number()
            payment_date = parser.get_payment_date()
            amount = parser.get_amount()
        except Exception as e:  # noqa
            errors.append(f"{line_number}: {e}")
            continue

        try:
            installment = ApartmentInstallment.objects.get(
                invoice_number=invoice_number
            )
        except ApartmentInstallment.DoesNotExist:
            errors.append(
                f"{line_number}: ApartmentInstallment with invoice number "
                f'"{invoice_number}" does not exist.'
            )
            continue

        Payment.objects.create(
            batch=payment_batch,
            apartment_installment=installment,
            payment_date=payment_date,
            amount=amount,
        )
        num_of_payments += 1

    if errors:
        raise SapPaymentDataParsingError("Parsing errors:\n" + "\n".join(errors))

    return num_of_payments
