import datetime
import pathlib
import unittest
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from apartment_application_service.pdf import _get_checkbox_checked_value
from apartment_application_service.pdf import PDFCurrencyField as CF
from application_form.enums import ApartmentReservationState
from application_form.models.reservation import ApartmentReservation
from application_form.tests.conftest import sell_apartments
from invoicing.enums import InstallmentType
from invoicing.tests.factories import ApartmentInstallmentFactory

from ..pdf.hitas import (
    create_hitas_complete_apartment_contract_pdf_from_data,
    create_hitas_contract_pdf,
    create_hitas_contract_pdf_from_data,
    HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME,
    HitasCompleteApartmentContractPDFData,
    HitasContractPDFData,
)
from .pdf_expected_texts_pypdfium import (
    HITAS_COMPLETE_APARTMENT_CONTRACT_EXPECTED_TEXTS,
    HITAS_CONTRACT_EXPECTED_TEXTS,
)
from .pdf_utils import get_cleaned_pdf_texts, remove_pdf_id

# This variable should be normally False, but can be set temporarily to
# True to override the expected test result PDF file.  This is useful
# when either the template has changed or the test data has changed and
# a new expected result PDF file needs to be generated.  Remember to
# revert this variable back to False to ensure that the test is
# actually testing the expected result.
OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE = False

my_dir = pathlib.Path(__file__).parent


CONTRACT_PDF_DATA = HitasContractPDFData(
    # 1
    occupant_1="Matti Meikäläinen",
    occupant_1_share_of_ownership="49%",
    occupant_1_address="Pöhkökatu 1 C 51",
    occupant_1_phone_number="040 123 4567",
    occupant_1_email="matti.meikalainen@meikä.fi",
    occupant_1_ssn_or_business_id="010101-1234",
    occupant_2="Maija Meikäläinen",
    occupant_2_share_of_ownership="51%",
    occupant_2_address="Möhkälekatu 2 F 64",
    occupant_2_phone_number="050 987 6543",
    occupant_2_email="maija.meikalainen@meikä.fi",
    occupant_2_ssn_or_business_id="020202-2345",
    #
    # 2
    project_housing_company="Asumiskolo Pöhkö",
    project_contract_business_id="0912770-2",
    project_address="Mörkötie 12",
    project_realty_id="123-456-789-0",
    housing_type_ownership=False,
    housing_type_rental=True,
    housing_shares="123–456",
    apartment_street_address="Mörkötie 12 C 51",
    apartment_structure="4h+k+s+yöpymisparvi",
    apartment_number="C 51",
    floor=5,
    living_area="125.3",
    other_space=None,
    other_space_area=None,
    project_contract_transfer_restriction_false=False,
    project_contract_transfer_restriction_true=True,
    project_contract_transfer_restriction_text="ks. yhtiöjärjestyksen 9-13.",
    project_contract_material_selection_later_false=True,
    project_contract_material_selection_later_true=False,
    project_contract_material_selection_description="myöhemmin",
    project_contract_material_selection_date=datetime.date(2022, 12, 19),
    #
    # 3
    sales_price=CF(euros=Decimal("1234.56")),
    loan_share=CF(euros=Decimal("2345.67")),
    debt_free_sales_price=CF(euros=Decimal("3456.78")),
    payment_1_label="Maksuerä 1",
    payment_1_amount=CF(euros=Decimal("4567.89")),
    payment_1_due_date=datetime.date(2020, 8, 19),
    payment_1_percentage=Decimal("12.5"),
    payment_2_label="Maksuerä 2",
    payment_2_amount=CF(euros=Decimal("5678.90")),
    payment_2_due_date=datetime.date(2020, 9, 3),
    payment_2_percentage=Decimal("25.0"),
    payment_3_label="Maksuerä 3",
    payment_3_amount=CF(euros=Decimal("6789.01")),
    payment_3_due_date=datetime.date(2020, 10, 3),
    payment_3_percentage=Decimal("37.5"),
    payment_4_label="Maksuerä 4",
    payment_4_amount=CF(euros=Decimal("7890.12")),
    payment_4_due_date=datetime.date(2020, 11, 3),
    payment_4_percentage=Decimal("50.0"),
    payment_5_label="Maksuerä 5",
    payment_5_amount=CF(euros=Decimal("8901.23")),
    payment_5_due_date=datetime.date(2020, 12, 3),
    payment_5_percentage=Decimal("62.5"),
    second_last_payment_label="6",
    second_last_payment_basis_sales_price=True,
    second_last_payment_basis_debt_free_sales_price=True,
    second_last_payment_dfsp_percentage=Decimal("72.5"),
    second_last_payment_dfsp_amount=CF(euros=Decimal("9012.34")),
    last_payment_label="7",
    last_payment_basis_sales_price=True,
    last_payment_basis_debt_free_sales_price=True,
    last_payment_dfsp_percentage=Decimal("82.5"),
    last_payment_dfsp_amount=CF(euros=Decimal("10123.45")),
    payment_bank_1="Nordea",
    payment_account_number_1="FI12 3456 7890 1234 56",
    payment_bank_2="Nordea",
    payment_account_number_2="FI34 5678 9012 3456 78",
    down_payment_amount=CF(euros=Decimal("1234.56")),
    #
    # 5
    project_contract_apartment_completion_selection_1=True,
    project_contract_apartment_completion_selection_1_date=datetime.date(2021, 3, 31),
    project_contract_apartment_completion_selection_2=False,
    project_contract_apartment_completion_selection_2_start=datetime.date(2021, 4, 1),
    project_contract_apartment_completion_selection_2_end=datetime.date(2021, 5, 31),
    project_contract_apartment_completion_selection_3=True,
    project_contract_apartment_completion_selection_3_date=datetime.date(2021, 6, 30),
    #
    # 9
    project_contract_depositary="Ö-Pankki Oyj",
    project_contract_repository="PL 123, 00020 Ö-Pankki",
    #
    # 15
    breach_of_contract_option_1=True,
    breach_of_contract_option_2=False,
    #
    # 17
    project_contract_collateral_type="kiinteistökiinnitys",
    project_contract_default_collateral="pankkitalletus 100 € Ä-Pankki Oyj:ssä",
    #
    # 19
    project_contract_construction_permit_requested=datetime.date(2020, 7, 1),
    #
    # 22
    project_contract_other_terms="Muita ehtoja ja myös sellasta",
    project_documents_delivered="ehkä",
    #
    # contract part "allekirjoitukset" (signings)
    signing_place_and_time="Mörkökylässä 1.7.2020",
    signing_buyers="Matti Meikäläinen & Maija Meikäläinen",
    salesperson="Mörkö",
    project_contract_collateral_bank_and_address="Ö-Pankki Oyj, PL 123, 00020 Ö-Pankki",
)

COMPLETE_CONTRACT_PDF_DATA = HitasCompleteApartmentContractPDFData(
    occupant_1="Matti Meikäläinen",
    occupant_1_share_of_ownership="49%",
    occupant_1_address="Pöhkökatu 1 C 51",
    occupant_1_phone_number="040 123 4567",
    occupant_1_ssn_or_business_id="010101-1234",
    occupant_1_email="matti.meikalainen@meikä.fi",
    occupant_2="Maija Meikäläinen",
    occupant_2_share_of_ownership="51%",
    occupant_2_address="Möhkälekatu 2 F 64",
    occupant_2_phone_number="050 987 6543",
    occupant_2_ssn_or_business_id="020202-2345",
    occupant_2_email="maija.meikalainen@meikä.fi",
    project_housing_company="Asumiskolo Pöhkö",
    project_contract_business_id="0912770-2",
    project_address="Mörkötie 12",
    project_realty_id="123-456-789-0",
    housing_type_ownership=False,
    housing_type_rental=True,
    housing_shares="123-456",
    apartment_number="C 51",
    apartment_street_address="Mörkötie 12 C 51",
    floor=5,
    apartment_structure="4h+k+s+yöpymisparvi",
    living_area="125.3",
    other_space="Muu tila",
    other_space_area="10.5",
    project_contract_transfer_restriction_false=False,
    project_contract_transfer_restriction_true=True,
    project_contract_transfer_restriction_text="Lunastusoikeus lisätiedot",
    project_contract_construction_permit_requested="12.1.2024",
    project_documents_delivered="Foo.pdf\nBar.pdf\nTest.docx",
    sales_price=CF(euros=Decimal("1234.56")),
    loan_share=CF(euros=Decimal("2345.67")),
    loan_share_and_sales_price=CF(euros=Decimal("3580.23")),
    buyer_has_paid_down_payment="1.1.2024",
    payment_terms_rest_of_price="Loppukauppahinnan maksuehdot ovat seuraavanlaiset...",
    payment_bank_1="Testi pankki",
    payment_account_number_1="FI21 1234 5600 0007 85",
    sales_price_x_0_02=False,
    debt_free_price_x_0_014=True,
    last_payment_dfsp_amount=CF(euros=Decimal("1234.56")),
    final_payment=CF(euros=Decimal("17.30")),
    payment_account_number_2="FI21 1234 5600 0007 87",
    credit_interest="12",
    transfer_of_shares="12.8.2025",
    transfer_of_posession="12.8.2025",
    breach_of_contract_option_1=True,
    breach_of_contract_option_2=False,
    project_contract_collateral_type="Kiinteisto kiinnitys",
    inability_to_pay_guarantee="Suorituskyvyttömyysvakuus",
    guarantee="Muu vakuus",
    guarantee_attachment_exists=True,
    guarantee_attachment_not_exists=False,
    project_built_according_to_regulations="Rakennettu säännösten mukaan",
    other_contract_terms="Muut sopimusehdot",
    documents="Ostaja on perehtynyt seuraaviin asiakirjoihin <lista asiakirjoista>",
    signing_place_and_time="22.1.2024 Helsinki",
    salesperson_signature="Markku Myyjä",
    occupants_signatures="Matti Meikäläinen",
    sales_price_paid="Kuitattu maksetuksi",
    sales_price_paid_place_and_time="Helsingissä 22.1.2024",
    sales_price_paid_salesperson_signature="Matti Myyjä",
    transfer_of_shares_confirmed="22.1.2024",
    transfer_of_shares_signature="Matti Meikäläinen",
)


class TesthitasCompleteApartmentContractPdfFromData(unittest.TestCase):
    def setUp(self) -> None:
        pdf = create_hitas_complete_apartment_contract_pdf_from_data(
            COMPLETE_CONTRACT_PDF_DATA,
        )
        self.pdf_content = pdf.getvalue()

        if OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE:
            write_file(
                "hitas_complete_apartment_contract_test_result.pdf", self.pdf_content
            )
            assert False, "Not testing, because PDF file was overridden."

        self.expected_pdf_content = read_file(
            "hitas_complete_apartment_contract_test_result.pdf"
        )

        return super().setUp()

    def test_pdf_content_is_not_empty(self):
        assert self.pdf_content

    def test_pdf_content_without_id_is_expected(self):
        generated_without_id = remove_pdf_id(self.pdf_content)
        expected_without_id = remove_pdf_id(self.expected_pdf_content)
        if generated_without_id != expected_without_id:
            # Don't assert a == b, because the output is too long to be
            # printed in the test output.
            assert False, "Invalid PDF content"

    def test_pdf_content_is_correct(self):
        # acquire a new version of this PDF array by running
        # python manage.py pdf_as_array application_form/tests/hitas_complete_apartment_contract_test_result.pdf  # noqa: E501
        assert (
            get_cleaned_pdf_texts(self.pdf_content)
            == HITAS_COMPLETE_APARTMENT_CONTRACT_EXPECTED_TEXTS
        )


@pytest.mark.django_db
def test_create_hitas_contract_complete_apartment_pdf():
    """
    Basic test to verify the feature doesn't crash
    """
    ownership_type = OwnershipType.HITAS.value
    apartment = ApartmentDocumentFactory(
        project_ownership_type=ownership_type,
        project_use_complete_contract=True,
    )

    apartments = [apartment]
    apartments.append(
        ApartmentDocumentFactory(
            project_ownership_type=ownership_type,
            project_use_complete_contract=True,
            project_uuid=apartment.project_uuid,
        )
    )

    sell_apartments(apartment.project_uuid, len(apartments))

    reservations = ApartmentReservation.objects.filter(
        apartment_uuid__in=[apt.uuid for apt in apartments],
        state=ApartmentReservationState.SOLD,
    )

    installment_due_date = date.today() + timedelta(days=30)
    installment_due_date_str = installment_due_date.strftime("%d.%m.%Y")
    installment_value = 10500
    installment_value_str = "10 500,00 €"
    installment_iban = "FI7271347440000296"
    for idx, res in enumerate(reservations):

        installment = ApartmentInstallmentFactory(
            apartment_reservation=res,
            type=InstallmentType.PAYMENT_1,
            # verify due_date = None is handled correctly
            due_date=installment_due_date if idx > 0 else None,
            value=installment_value,
            account_number=installment_iban,
        )

    for idx, res in enumerate(reservations):
        pdf_data = create_hitas_contract_pdf(
            res, "Vantaa", "2025-08-21", get_user_model().objects.first()
        )

        pdf_texts = get_cleaned_pdf_texts(pdf_data.getvalue())

        if idx == 1:
            assert (
                f"{installment.type.label} {installment_due_date_str} {installment_value_str}"
                in pdf_texts
            )
        else:
            assert f"{installment.type.label} {installment_value_str}" in pdf_texts
    pass


class TesthitasContractPdfFromData(unittest.TestCase):
    def setUp(self) -> None:
        pdf = create_hitas_contract_pdf_from_data(
            CONTRACT_PDF_DATA, HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME
        )
        self.pdf_content = pdf.getvalue()

        if OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE:
            write_file("hitas_contract_test_result.pdf", self.pdf_content)
            assert False, "Not testing, because PDF file was overridden."

        self.expected_pdf_content = read_file("hitas_contract_test_result.pdf")

        return super().setUp()

    def test_pdf_content_is_not_empty(self):
        assert self.pdf_content

    def test_pdf_content_text_is_correct(self):
        # acquire a new version of this PDF array by running
        # python manage.py pdf_as_array application_form/tests/hitas_contract_test_result.pdf  # noqa: E501
        assert get_cleaned_pdf_texts(self.pdf_content) == HITAS_CONTRACT_EXPECTED_TEXTS

    def test_pdf_content_without_id_is_expected(self):
        generated_without_id = remove_pdf_id(self.pdf_content)
        expected_without_id = remove_pdf_id(self.expected_pdf_content)
        if generated_without_id != expected_without_id:
            # Don't assert a == b, because the output is too long to be
            # printed in the test output.
            assert False, "Invalid PDF content"


def test_get_checkbox_checked_value():

    # NOTE: There is no universal value for a checked checkbox
    # https://stackoverflow.com/a/48412434/4558221
    # Try to mitigate this by figuring out
    # what the value for the "checked" state is
    # Its stored in the key "/AP" and its "/On", "/Yes" or "/1"

    @dataclass
    class Annotation:
        AP: dict

    assert _get_checkbox_checked_value(Annotation({"/D": {"/Yes": {}}})) == "/Yes"
    assert _get_checkbox_checked_value(Annotation({"/D": {"/1": {}}})) == "/1"
    assert _get_checkbox_checked_value(Annotation({"/D": {"foo": {}}})) == "/On"

    pass


def read_file(file_name: str) -> bytes:
    with open(my_dir / file_name, "rb") as fp:
        return fp.read()


def write_file(file_name: str, data: bytes) -> None:  # pragma: no cover
    with open(my_dir / file_name, "wb") as fp:
        fp.write(data)
