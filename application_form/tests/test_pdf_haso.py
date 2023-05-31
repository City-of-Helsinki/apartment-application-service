import datetime
import pathlib
import re
import subprocess
import unittest
from decimal import Decimal
from typing import List

import pytest

from apartment_application_service.pdf import PDFCurrencyField as CF

from ..pdf.haso import create_haso_contract_pdf_from_data, HasoContractPDFData

# This variable should be normally False, but can be set temporarily to
# True to override the expected test result PDF file.  This is useful
# when either the template has changed or the test data has changed and
# a new expected result PDF file needs to be generated.  Remember to
# revert this variable back to False to ensure that the test is
# actually testing the expected result.
OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE = False

my_dir = pathlib.Path(__file__).parent


CONTRACT_PDF_DATA = HasoContractPDFData(
    occupant_1="Asta Asukas",
    occupant_1_street_address="Astankuja 12a5",
    occupant_1_phone_number="040 123 4567",
    occupant_1_email="asta.asukas@esimerkki.fi",
    occupant_1_ssn="190395-999X",
    occupant_2="Bertta Asukas",
    occupant_2_street_address="Bertankaari 8 C 12",
    occupant_2_phone_number="050 987 6543",
    occupant_2_email="bertta.asukas@toinen.fi",
    occupant_2_ssn="240900A8883",
    right_of_residence_number="1234",
    project_housing_company="Lämmin Koti Oy",
    project_street_address="Lämpimäntie 9 00100 Helsinki",
    apartment_number="C 12",
    apartment_structure="4h+k+s",
    living_area=125.3,
    floor=77,
    right_of_occupancy_payment=CF(cents=4521400, suffix=" €"),
    right_of_occupancy_payment_text=(
        "neljäkymmentäviisituhatta kaksisataaneljätoista euroa"
    ),
    payment_due_date=datetime.date(2020, 8, 19),
    installment_amount=CF(euros=Decimal("46537.45")),
    right_of_occupancy_fee=CF(cents=78950, suffix=" € / kk"),
    right_of_occupancy_fee_m2=CF(cents=1011, suffix=" € /m\u00b2/kk"),
    project_contract_apartment_completion="31.3.2021 — 31.5.2021",
    signing_place="Helsinki",
    project_acc_salesperson="Maija Myyjä",
    project_contract_other_terms="Kaikenlaisia ehtoja",
    project_contract_usage_fees="400 € / kk",
    project_contract_right_of_occupancy_payment_verification="Tarkistusta",
    signing_text="",
    signing_time=None,
    approval_date="1.7.2020",
    alterations="1200,00",
    index_increment=Decimal("123.45"),
)


class TestHasoContractPdfFromData(unittest.TestCase):
    def setUp(self) -> None:
        pdf = create_haso_contract_pdf_from_data(CONTRACT_PDF_DATA)
        self.pdf_content = pdf.getvalue()

        if OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE:
            write_file("haso_contract_test_result.pdf", self.pdf_content)
            assert False, "Not testing, because PDF file was overridden."

        self.expected_pdf_content = read_file("haso_contract_test_result.pdf")

        return super().setUp()

    def test_pdf_content_is_not_empty(self):
        assert self.pdf_content

    def test_pdf_content_text_is_correct(self):
        assert get_cleaned_pdf_texts(self.pdf_content) == [
            "Asta Asukas Bertta Asukas",
            "Astankuja 12a5 Bertankaari 8 C 12",
            "040 123 4567 050 987 6543",
            "asta.asukas@esimerkki.fi bertta.asukas@toinen.fi",
            "190395-999X 240900A8883",
            "1.7.2020 1234",
            "Lämmin Koti Oy",
            "Lämpimäntie 9 00100 Helsinki C 12",
            "4h+k+s 125.3 77",
            "neljäkymmentäviisituhatta kaksisataaneljätoista euroa 45 214,00 €",
            "123,45",
            "1200,00",
            "19.8.2020 46 537,45",
            "789,50 € / kk 10,11 € /m²/kk",
            "400 € / kk",
            "31.3.2021 — 31.5.2021",
            "Tarkistusta",
            "Kaikenlaisia ehtoja",
            "Helsinki",
            "Maija Myyjä",
            "Asta Asukas Bertta Asukas",
        ]

    def test_pdf_content_without_id_is_expected(self):
        generated_without_id = remove_pdf_id(self.pdf_content)
        expected_without_id = remove_pdf_id(self.expected_pdf_content)
        if generated_without_id != expected_without_id:
            # Don't assert a == b, because the output is too long to be
            # printed in the test output.
            assert False, "Invalid PDF content"


def read_file(file_name: str) -> bytes:
    with open(my_dir / file_name, "rb") as fp:
        return fp.read()


def write_file(file_name: str, data: bytes) -> None:  # pragma: no cover
    with open(my_dir / file_name, "wb") as fp:
        fp.write(data)


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
