import io
import re
from datetime import date
from typing import List, Union

import pypdfium2 as pdfium
from faker import Faker

from apartment.elastic.documents import ApartmentDocument
from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.models.reservation import ApartmentReservation
from application_form.pdf.haso import get_haso_contract_pdf_data, HasoContractPDFData
from application_form.pdf.hitas import (
    get_hitas_contract_pdf_data,
    HitasCompleteApartmentContractPDFData,
    HitasContractPDFData,
)
from application_form.tests.factories import ApartmentReservationFactory
from invoicing.enums import InstallmentType
from invoicing.tests.factories import ApartmentInstallmentFactory
from users.tests.factories import UserFactory


def assert_pdf_has_text(pdf: bytes, text: str) -> bool:
    """
    Check if the PDF file contains the given text.
    """
    pdf_text_content = "\n".join(get_cleaned_pdf_texts(pdf))
    assert (
        text in pdf_text_content
    ), f"Text {text!r} was not found in PDF text:\n{pdf_text_content}"


def get_cleaned_pdf_texts(pdf: bytes) -> List[str]:
    """
    Extract cleaned text lines from a PDF.

    Parameters:
        pdf (bytes): PDF file contents.

    Returns:
        cleaned (List[str]): Non-empty whitespace-normalized lines.
    """
    result = []
    for text_line in get_pdf_text_lines(pdf):
        cleaned = re.sub(r"\s+", " ", text_line).strip()
        if cleaned:
            result.append(cleaned)
    return result


def get_pdf_text_lines(pdf: bytes) -> List[str]:
    """
    Extract raw text lines from a PDF using pypdfium2.

    Flattens AcroForm fields into page content and reloads the PDF so
    NeedAppearances field values are included in extracted text.

    Parameters:
        pdf (bytes): PDF file contents.

    Returns:
        lines (List[str]): Raw text lines from all pages.
    """
    doc = pdfium.PdfDocument(pdf)
    try:
        doc.init_forms()
        for page in doc:
            page.flatten()
            page.close()
        buffer = io.BytesIO()
        doc.save(buffer)
    finally:
        doc.close()

    flattened = pdfium.PdfDocument(buffer.getvalue())
    try:
        lines: List[str] = []
        for page in flattened:
            textpage = page.get_textpage()
            try:
                text = textpage.get_text_bounded()
            finally:
                textpage.close()
            lines.extend(text.splitlines())
            page.close()
        return lines
    finally:
        flattened.close()


def remove_pdf_id(pdf: bytes) -> bytes:
    """
    Remove the /ID entry from the PDF file.
    """
    return re.sub(rb"/ID\s+\[<[^]]+>\]", b"", pdf)


def set_up_contract_pdf_test_data(
    ownership_type: Union[OwnershipType, None] = OwnershipType.HASO,
    apartment: Union[ApartmentDocument, None] = None,
    reservation: Union[ApartmentReservation, None] = None,
    salesperson: Union[str, None] = None,
    sales_price_paid_place: Union[str, None] = None,
    sales_price_paid_time: Union[str, None] = None,
) -> Union[
    HitasContractPDFData, HitasCompleteApartmentContractPDFData, HasoContractPDFData
]:  # noqa: E501

    faker = Faker()
    if not apartment:
        apartment = ApartmentDocumentFactory(
            project_ownership_type=ownership_type.value
        )

    if not reservation:
        reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    installment_types = [
        InstallmentType.PAYMENT_1,
        InstallmentType.PAYMENT_2,
        InstallmentType.PAYMENT_3,
        InstallmentType.PAYMENT_4,
        InstallmentType.PAYMENT_5,
        InstallmentType.PAYMENT_6,
        InstallmentType.PAYMENT_7,
    ]
    for installment_type in installment_types:
        ApartmentInstallmentFactory(
            apartment_reservation=reservation,
            value=100_000,
            type=installment_type,
        )
        pass

    if not salesperson:
        salesperson = UserFactory()

    if not sales_price_paid_place:
        sales_price_paid_place = faker.city()

    if not sales_price_paid_time:
        sales_price_paid_time = f"{date.today():%d.%m.%Y}"

    func = {
        OwnershipType.HASO: get_haso_contract_pdf_data,
        OwnershipType.HITAS: get_hitas_contract_pdf_data,
    }[ownership_type]

    pdf_data = func(
        reservation,
        salesperson=salesperson,
        sales_price_paid_place=sales_price_paid_place,
        sales_price_paid_time=sales_price_paid_time,
    )

    return pdf_data
