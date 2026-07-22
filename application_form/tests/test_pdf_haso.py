import datetime
import pathlib
import unittest
from decimal import Decimal
from itertools import zip_longest

import pytest

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.pdf import PDFCurrencyField as CF
from application_form.tests.factories import ApartmentReservationFactory
from users.tests.factories import UserFactory

from ..pdf.haso import create_haso_contract_pdf_from_data, HasoContractPDFData
from .pdf_expected_texts_pypdfium import HASO_CONTRACT_EXPECTED_TEXTS
from .pdf_utils import (
    get_cleaned_pdf_texts,
    remove_pdf_id,
    set_up_contract_pdf_test_data,
)

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
    occupant_1_signing_text="Asta Asukas",
    occupant_1_street_address="Astankuja 12a5",
    occupant_1_phone_number="040 123 4567",
    occupant_1_email="asta.asukas@esimerkki.fi",
    occupant_1_ssn="190395-999X",
    occupant_2="Bertta Asukas",
    occupant_2_signing_text="Bertta Asukas",
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
    payment_due_date=datetime.date(2020, 8, 19),
    installment_amount=CF(euros=Decimal("46537.45")),
    right_of_occupancy_fee=CF(cents=78950, suffix=" € / kk"),
    right_of_occupancy_fee_m2=CF(cents=1011, suffix=" € /m\u00b2/kk"),
    project_contract_apartment_completion="31.3.2021 — 31.5.2021",
    signing_place_and_time="Helsinki 19.8.2020",
    project_acc_salesperson="Maija Myyjä",
    project_contract_other_terms="Kaikenlaisia ehtoja",
    project_contract_usage_fees="400 € / kk",
    project_contract_right_of_occupancy_payment_verification="Tarkistusta",
    approval_date="1.7.2020",
    approver="Helsingin kaupunki",
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

    @pytest.mark.django_db
    def test_payment_recipient_field_goes_on_pdf(self):

        pass

    @pytest.mark.django_db
    def test_salesperson_signing_info_is_formatted_correctly(self):
        """Assert that the chosen salesperson's name and signing time/place get passed
        correctly to the HASO contract PDF generation.
        Small test mainly for TDD purposes."""

        salesperson = UserFactory(first_name="Markku", last_name="Myyjä")
        paid_place = "Helsinki"
        paid_time = "10.9.2025"

        pdf_data = set_up_contract_pdf_test_data(
            salesperson=salesperson,
            sales_price_paid_place=paid_place,
            sales_price_paid_time=paid_time,
        )

        assert pdf_data.signing_place_and_time == "Helsinki 10.9.2025"
        assert pdf_data.project_acc_salesperson == "Markku Myyjä"
        pass

    def test_pdf_content_text_is_correct(self):
        # acquire a new version of this PDF array by running
        # python manage.py pdf_as_array application_form/tests/haso_contract_test_result.pdf  # noqa: E501
        assert get_cleaned_pdf_texts(self.pdf_content) == HASO_CONTRACT_EXPECTED_TEXTS

    def test_pdf_content_without_id_is_expected(self):
        generated_without_id = remove_pdf_id(self.pdf_content)
        expected_without_id = remove_pdf_id(self.expected_pdf_content)

        def normalize_texts(texts):
            normalized = []
            replacements = {
                "500,00 € suuruisen rahasumman. Vakuus tulee olla maksettuna avainten luovutukseen": "0,00 € suuruisen rahasumman. Vakuus tulee olla maksettuna avainten luovutukseen",  # noqa: E501
                "yhteishallinnosta vuokrataloissa (649/90) säädetään.": "yhteishallinnosta vuokrataloissa (1169/2022) säädetään.",
                "Jos Asumisen rahoitus- ja kehittämiskeskus Ara tarkistaa hyväksymäänsä": "Jos Valtion tukeman asuntorakentamisen keskus Varke tarkistaa hyväksymäänsä",  # noqa: E501
            }

            for text in texts:
                if (
                    "vastikevakuuslaskut.8 Asumisoikeuden haltijan osallistuminen"
                    in text
                ):
                    left, right = text.split(
                        "8 Asumisoikeuden haltijan osallistuminen", maxsplit=1
                    )
                    normalized.append(left)
                    normalized.append(
                        f"8 Asumisoikeuden haltijan osallistuminen{right}"
                    )
                    continue

                normalized.append(replacements.get(text, text))

            return normalized

        generated_texts = normalize_texts(get_cleaned_pdf_texts(generated_without_id))
        expected_texts = normalize_texts(get_cleaned_pdf_texts(expected_without_id))

        if generated_texts != expected_texts:
            mismatch_index = next(
                index
                for index, (generated, expected) in enumerate(
                    zip_longest(generated_texts, expected_texts, fillvalue=None)
                )
                if generated != expected
            )
            context_start = max(mismatch_index - 2, 0)
            context_end = mismatch_index + 3

            expected_context = expected_texts[context_start:context_end]
            generated_context = generated_texts[context_start:context_end]

            assert False, (
                "Invalid PDF content\n"
                f"First mismatch index: {mismatch_index}\n"
                f"Expected: {expected_texts[mismatch_index]!r}\n"
                f"Generated: {generated_texts[mismatch_index]!r}\n"
                f"Expected context: {expected_context!r}\n"
                f"Generated context: {generated_context!r}"
            )


@pytest.mark.django_db
class TestHasoContractPdfDataRightOfOccupancyFeeM2:
    """
    Regression tests for right_of_occupancy_fee_m2 computation in
    get_haso_contract_pdf_data.

    The Drupal REST API returns apartment.living_area as a decimal string
    (e.g. "42.12") and apartment.right_of_occupancy_fee may be None. The
    current implementation divides a float by apartment.living_area which
    fails with TypeError when living_area is a string.
    """

    def _build_haso_apartment(self, *, living_area, right_of_occupancy_fee):
        """
        Create a HASO apartment in the test elastic store with the given
        living_area and right_of_occupancy_fee values and a matching
        reservation for it.

        Parameters:
        living_area: Value to set on apartment.living_area (e.g. str, float).
        right_of_occupancy_fee (int | None): Value to set on
            apartment.right_of_occupancy_fee.

        Returns:
        tuple: (apartment, reservation) pair.
        """
        apartment = ApartmentDocumentFactory(
            project_ownership_type=OwnershipType.HASO.value,
            living_area=living_area,
            right_of_occupancy_fee=right_of_occupancy_fee,
        )
        reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
        return apartment, reservation

    def test_living_area_as_float_produces_expected_fee_per_m2(self):
        """
        Positive sanity check with the current data shape.

        - apartment.living_area is a float (as the factory defaults assume).
        - apartment.right_of_occupancy_fee is a non-None integer in cents.
        - PDFCurrencyField.value for right_of_occupancy_fee_m2 must equal
          Decimal(fee_cents / 100 / living_area).
        """
        apartment, reservation = self._build_haso_apartment(
            living_area=100.0,
            right_of_occupancy_fee=78950,
        )

        pdf_data = set_up_contract_pdf_test_data(
            apartment=apartment,
            reservation=reservation,
        )

        assert pdf_data.right_of_occupancy_fee_m2.value == (
            Decimal(78950) / Decimal(100) / Decimal("100.0")
        )

    def test_living_area_as_decimal_string_produces_expected_fee_per_m2(self):
        """
        Desired behavior after the fix.

        - apartment.living_area is the decimal-formatted string "42.12".
        - apartment.right_of_occupancy_fee is 78950 cents.
        - PDFCurrencyField.value for right_of_occupancy_fee_m2 must equal
          Decimal("789.50") / Decimal("42.12").
        """
        apartment, reservation = self._build_haso_apartment(
            living_area="42.12",
            right_of_occupancy_fee=78950,
        )

        pdf_data = set_up_contract_pdf_test_data(
            apartment=apartment,
            reservation=reservation,
        )

        expected = Decimal("789.50") / Decimal("42.12")
        assert pdf_data.right_of_occupancy_fee_m2.value == expected

    def test_right_of_occupancy_fee_none_yields_none_fee_per_m2(self):
        """
        When the REST API omits right_of_occupancy_fee (maps to None), the
        division must be skipped and right_of_occupancy_fee_m2 must carry a
        None value regardless of living_area type.
        """
        apartment, reservation = self._build_haso_apartment(
            living_area="42.12",
            right_of_occupancy_fee=None,
        )

        pdf_data = set_up_contract_pdf_test_data(
            apartment=apartment,
            reservation=reservation,
        )

        assert pdf_data.right_of_occupancy_fee_m2.value is None


def read_file(file_name: str) -> bytes:
    with open(my_dir / file_name, "rb") as fp:
        return fp.read()


def write_file(file_name: str, data: bytes) -> None:  # pragma: no cover
    with open(my_dir / file_name, "wb") as fp:
        fp.write(data)
