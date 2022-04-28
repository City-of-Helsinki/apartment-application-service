from datetime import date, datetime, timedelta
from django.conf import settings
from typing import Union

from invoicing.enums import InstallmentType

REFERENCE_DOCUMENT_NUMBER_LENGTH = 20  # Document says 16


def create_reference_document_number(document_date: datetime, reference: str) -> str:
    if not document_date:
        raise ValueError("document_date cannot be null.")
    if not reference:
        raise ValueError("reference cannot be null or empty.")

    reference_document_number = (
        f"{settings.SAP.get('COMPANY_CODE')}"
        f"{settings.SAP.get('DOCUMENT_TYPE')}"
        f"{settings.SAP.get('SENDER_ID')[-3:]}"
        f"{document_date.strftime('%y')}"
        f"{reference.zfill(9)}"
    )

    if len(reference_document_number) != REFERENCE_DOCUMENT_NUMBER_LENGTH:
        raise ValueError(
            f"reference_document_number length is not "
            f"{REFERENCE_DOCUMENT_NUMBER_LENGTH}: {len(reference_document_number)}."
        )

    return reference_document_number


def get_base_line_date_string(due_date: Union[datetime, date]) -> str:
    payment_term = settings.SAP.get("PAYMENT_TERMS")
    if payment_term == "N073":
        result = due_date - timedelta(days=10)
    else:
        raise ValueError("PAYMENT_TERMS '{payment_term}' is not defined.")

    result = result.strftime("%Y%m%d")

    return result


def get_installment_type_text(installment_type: InstallmentType) -> str:  # noqa: C901
    if installment_type is InstallmentType.PAYMENT_1:
        result = "1. erä"
    elif installment_type is InstallmentType.PAYMENT_2:
        result = "2. erä"
    elif installment_type is InstallmentType.PAYMENT_3:
        result = "3. erä"
    elif installment_type is InstallmentType.PAYMENT_4:
        result = "4. erä"
    elif installment_type is InstallmentType.PAYMENT_5:
        result = "5. erä"
    elif installment_type is InstallmentType.PAYMENT_6:
        result = "6. erä"
    elif installment_type is InstallmentType.PAYMENT_7:
        result = "7. erä"
    elif installment_type is InstallmentType.DEPOSIT:
        result = "Vakuusmaksu"
    elif installment_type is InstallmentType.DOWN_PAYMENT:
        result = "Käsiraha"
    elif installment_type is InstallmentType.FOR_INVOICING:
        result = "Laskutettava"
    elif installment_type is InstallmentType.LATE_PAYMENT_INTEREST:
        result = "Viivästyskorko"
    elif installment_type is InstallmentType.REFUND:
        result = "Hyvitys"
    elif installment_type is InstallmentType.RESERVATION_FEE:
        result = "Varausmaksu"
    elif installment_type is InstallmentType.RIGHT_OF_RESIDENCE_FEE:
        result = "AO-maksu"
    else:
        raise ValueError("installment_type '{installment_type}' is not defined.")
    return result