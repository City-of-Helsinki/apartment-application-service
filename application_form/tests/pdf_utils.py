from datetime import date
import re
import subprocess
from typing import List, Union
from faker import Faker
from apartment.elastic.documents import ApartmentDocument
from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.models.reservation import ApartmentReservation
from application_form.pdf.haso import HasoContractPDFData, get_haso_contract_pdf_data
from application_form.pdf.hitas import HitasCompleteApartmentContractPDFData, HitasContractPDFData, get_hitas_contract_pdf_data
from application_form.tests.factories import ApartmentReservationFactory
from invoicing.enums import InstallmentType
from invoicing.tests.factories import ApartmentInstallmentFactory
import pytest
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
    result = []
    for text_line in get_pdf_text_lines(pdf):
        cleaned = re.sub(r"\s+", " ", text_line).strip()
        if cleaned:
            result.append(cleaned)
    return result


def get_pdf_text_lines(pdf: bytes) -> List[str]:
    pdftotext = "pdftotext"
    try:
        retcode = subprocess.call([pdftotext, "-v"], stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        return pytest.skip("pdftotext is not available")
    if retcode != 0:
        return pytest.skip("pdftotext not functioning")

    process = subprocess.Popen(
        [pdftotext, "-layout", "-", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    (stdout, stderr) = process.communicate(input=pdf)
    if process.returncode != 0:
        msg = f"pdftotext failed with code {process.returncode}: {stderr}"
        raise RuntimeError(msg)
    return stdout.decode("utf-8", errors="replace").splitlines()


def remove_pdf_id(pdf: bytes) -> bytes:
    """
    Remove the /ID entry from the PDF file.
    """
    return re.sub(rb"/ID\s+\[<[^]]+>\]", b"", pdf)


def set_up_contract_pdf_test_data(
        ownership_type:Union[OwnershipType, None]=OwnershipType.HASO,
        apartment: Union[ApartmentDocument, None]=None,
        reservation: Union[ApartmentReservation, None]=None,
        salesperson:Union[str, None]=None,
        sales_price_paid_place:Union[str, None]=None,
        sales_price_paid_time:Union[str, None]=None
    ) -> Union[HitasContractPDFData, HitasCompleteApartmentContractPDFData, HasoContractPDFData]:  # noqa: E501

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
            OwnershipType.HITAS: get_hitas_contract_pdf_data
        }[ownership_type]

        pdf_data = func(
            reservation,
            salesperson=salesperson,
            sales_price_paid_place=sales_price_paid_place,
            sales_price_paid_time=sales_price_paid_time,
        )

        return pdf_data
