import dataclasses
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from num2words import num2words
from typing import ClassVar, Dict, Union

from apartment.elastic.queries import get_apartment
from apartment_application_service.pdf import create_pdf, PDFCurrencyField, PDFData
from apartment_application_service.utils import SafeAttributeObject
from application_form.models import ApartmentReservation
from invoicing.enums import InstallmentType, InstallmentUnit
from invoicing.models import ProjectInstallmentTemplate
from invoicing.utils import remove_exponent

HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME = "hitas_contract_template.pdf"


@dataclasses.dataclass
class HitasContractPDFData(PDFData):
    # contract part 1
    occupant_1: str
    occupant_1_share_of_ownership = Union[str, None]
    occupant_1_address: str
    occupant_1_phone_number: str
    occupant_1_email: str
    occupant_1_ssn_or_business_id: Union[str, None]
    occupant_2: Union[str, None]
    occupant_2_share_of_ownership = Union[str, None]
    occupant_2_address: Union[str, None]
    occupant_2_phone_number: Union[str, None]
    occupant_2_email: Union[str, None]
    occupant_2_ssn_or_business_id: Union[str, None]

    # 2
    project_housing_company: Union[str, None]
    project_contract_business_id: Union[str, None]
    project_address: Union[str, None]
    project_realty_id: Union[str, None]
    housing_type_ownership: Union[bool, None]
    housing_type_rental: Union[bool, None]
    housing_shares: Union[str, None]
    apartment_street_address: Union[str, None]
    apartment_structure: Union[str, None]
    apartment_number: Union[str, None]
    floor: Union[int, None]
    living_area: Union[str, None]
    other_space: Union[str, None]
    other_space_area: Union[str, None]
    project_contract_transfer_restriction_false: Union[bool, None]
    project_contract_transfer_restriction_true: Union[bool, None]
    project_contract_material_selection_later_false: Union[bool, None]
    project_contract_material_selection_later_true: Union[bool, None]
    project_contract_material_selection_description: Union[str, None]

    # 3
    sales_price: Union[PDFCurrencyField, None]
    loan_share: Union[PDFCurrencyField, None]
    debt_free_sales_price: Union[PDFCurrencyField, None]
    payment_1_label: Union[str, None]
    payment_1_amount: Union[PDFCurrencyField, None]
    payment_1_due_date: Union[date, None]
    payment_1_percentage: Union[Decimal, None]
    payment_2_label: Union[str, None]
    payment_2_amount: Union[PDFCurrencyField, None]
    payment_2_due_date: Union[date, None]
    payment_2_percentage: Union[Decimal, None]
    payment_3_label: Union[str, None]
    payment_3_amount: Union[PDFCurrencyField, None]
    payment_3_due_date: Union[date, None]
    payment_3_percentage: Union[Decimal, None]
    payment_4_label: Union[str, None]
    payment_4_amount: Union[PDFCurrencyField, None]
    payment_4_due_date: Union[date, None]
    payment_4_percentage: Union[Decimal, None]
    payment_5_label: Union[str, None]
    payment_5_amount: Union[PDFCurrencyField, None]
    payment_5_due_date: Union[date, None]
    payment_5_percentage: Union[Decimal, None]
    payment_6_amount: Union[PDFCurrencyField, None]
    payment_6_due_date: Union[date, None]
    payment_6_percentage: Union[Decimal, None]
    payment_7_amount: Union[PDFCurrencyField, None]
    payment_7_due_date: Union[date, None]
    payment_7_percentage: Union[Decimal, None]
    second_last_payment_basis_sales_price: Union[bool, None]
    second_last_payment_basis_debt_free_sales_price: Union[bool, None]
    last_payment_basis_sales_price: Union[bool, None]
    last_payment_basis_debt_free_sales_price: Union[bool, None]
    payment_bank_1: Union[str, None]
    payment_account_number_1: Union[str, None]
    payment_bank_2: Union[str, None]
    payment_account_number_2: Union[str, None]
    down_payment_amount: Union[PDFCurrencyField, None]

    # 5
    project_contract_apartment_completion_selection_1: Union[bool, None]
    project_contract_apartment_completion_selection_1_date: Union[date, None]
    project_contract_apartment_completion_selection_2: Union[bool, None]
    project_contract_apartment_completion_selection_2_start: Union[date, None]
    project_contract_apartment_completion_selection_2_end: Union[date, None]
    project_contract_apartment_completion_selection_3: Union[bool, None]
    project_contract_apartment_completion_selection_3_date: Union[date, None]

    # 9
    project_contract_depositary: Union[str, None]
    project_contract_repository: Union[str, None]

    # 15
    breach_of_contract_option_1: Union[bool, None]
    breach_of_contract_option_2: Union[bool, None]

    # 17
    project_contract_collateral_type: Union[str, None]
    project_contract_collateral_bank_and_address: Union[str, None]
    project_contract_default_collateral: Union[str, None]

    # 19
    project_contract_construction_permit_requested: Union[date, None]

    # 22
    project_contract_other_terms: Union[str, None]
    project_documents_delivered: Union[str, None]

    # contract part "allekirjoitukset" (signings)
    signing_place_and_time: Union[str, None]
    signing_text: str
    salesperson: Union[str, None]

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "occupant_1": "Ostaja 1",
        "occupant_1_share_of_ownership": "Ostaja 1 omistusosuus",
        "occupant_1_address": "Ostaja 1 osoite",
        "occupant_1_phone_number": "Ostaja 1 puhelin",
        "occupant_1_email": "Ostaja 1 sähköposti",
        "occupant_1_ssn_or_business_id": "Ostaja 1 sotu",
        "occupant_2": "Ostaja 2",
        "occupant_2_share_of_ownership": "Ostaja 2 omistusosuus",
        "occupant_2_address": "Ostaja 2 osoite",
        "occupant_2_phone_number": "Ostaja 2 puhelin",
        "occupant_2_email": "Ostaja 2 sähköposti",
        "occupant_2_ssn_or_business_id": "Ostaja 2 sotu",
        "apartment_number": "asunto",
        "project_housing_company": "Yhtiön osoite",  # TODO puuttuu ?
        "project_contract_business_id": "Yhtiön y-tunnus",
        "project_address": "Yhtiön osoite",
        "project_realty_id": "kiinteistötunnus",
        "housing_type_ownership": "Check Box36",
        "housing_type_rental": "Check Box37",
        "housing_shares": "osakkeiden numerot",
        "apartment_street_address": "Asunnon osoite",
        "floor": "Text19",
        "apartment_structure": "huonetyyppi",
        "living_area": "Text20",
        "other_space": "Text21",
        "other_space_area": "Text22",
        "project_contract_transfer_restriction_false": "Check Box34",
        "project_contract_transfer_restriction_true": "Check Box35",
        "project_contract_material_selection_later_false": "Check Box38",
        "project_contract_material_selection_later_true": "Check Box39",
        "project_contract_material_selection_description": "Täsmennyksen ajankohta",
        "sales_price": "Text25",
        "loan_share": "yhtiölaina",
        "debt_free_sales_price": "velaton hinta",
        "payment_1_label": "Text40",
        "payment_2_label": "Text41",
        "payment_3_label": "eräpäivä3",
        "payment_4_label": "eräpäivä 4",
        "payment_5_label": "eräpäivä 5",
        "payment_1_amount": "Text54",
        "payment_2_amount": "Text55",
        "payment_3_amount": "Text1",
        "payment_4_amount": "Text2",
        "payment_5_amount": "Text3",
        "payment_6_amount": "Text6",
        "payment_7_amount": "Text16",
        "payment_1_due_date": "Text42",
        "payment_2_due_date": "Text43",
        "payment_3_due_date": "Text44",
        "payment_4_due_date": "Text45",
        "payment_5_due_date": "Text46",
        "payment_6_due_date": "Text52",
        "payment_7_due_date": "Text53",
        "payment_1_percentage": "Text47",
        "payment_2_percentage": "Text48",
        "payment_3_percentage": "Text49",
        "payment_4_percentage": "Text50",
        "payment_5_percentage": "Text51",
        "payment_6_percentage": "Text6",
        "payment_7_percentage": "Text16",
        "second_last_payment_basis_sales_price": "Check Box17",
        "second_last_payment_basis_debt_free_sales_price": "Check Box19",
        "last_payment_basis_sales_price": "Check Box18",
        "last_payment_basis_debt_free_sales_price": "Check Box20",
        "payment_bank_1": "Pankkitili1",
        "payment_account_number_1": "Text23",
        "payment_bank_2": "pankkitili2",
        "payment_account_number_2": "Text24",
        "down_payment_amount": "Text26",
        "project_contract_apartment_completion_selection_1": "Check Box27",
        "project_contract_apartment_completion_selection_1_date": "Text29",
        "project_contract_apartment_completion_selection_2": "Check Box28",
        "project_contract_apartment_completion_selection_2_start": "Text30",
        "project_contract_apartment_completion_selection_2_end": "Text31",
        "project_contract_apartment_completion_selection_3": "Check Box32",
        "project_contract_apartment_completion_selection_3_date": "Text34",
        "project_contract_depositary": "Turva-asiakirjojen säilyttäjä",
        "project_contract_repository": "osoite pankki",
        "breach_of_contract_option_1": "Check Box2",
        "breach_of_contract_option_2": "Check Box3",
        "project_contract_collateral_type": "vakuuden laji",
        "project_contract_collateral_bank_and_address": "Text35",
        "project_contract_default_collateral": "suorituskyvyttömyysvakuutus",
        "project_contract_construction_permit_requested": "Text4",
        "project_contract_other_terms": "22 Muut ehdot Uatkoa",
        "project_documents_delivered": "Kauppakirjan liitteet",
        "signing_place_and_time": "Text7",
        "signing_text": "oikeaksi todistetaan",
        "salesperson": "Text5",
    }


def create_hitas_contract_pdf(reservation: ApartmentReservation) -> BytesIO:
    customer = SafeAttributeObject(reservation.customer)
    primary_profile = SafeAttributeObject(customer.primary_profile)
    secondary_profile = SafeAttributeObject(customer.secondary_profile)
    apartment = SafeAttributeObject(
        get_apartment(reservation.apartment_uuid, include_project_fields=True)
    )

    project_installment_templates = ProjectInstallmentTemplate.objects.filter(
        project_uuid=apartment.project_uuid
    )

    payment_1, payment_2, payment_3, payment_4, payment_5, payment_6, payment_7 = [
        SafeAttributeObject(
            reservation.apartment_installments.filter(type=payment_type).first()
        )
        for payment_type in (
            InstallmentType.PAYMENT_1,
            InstallmentType.PAYMENT_2,
            InstallmentType.PAYMENT_3,
            InstallmentType.PAYMENT_4,
            InstallmentType.PAYMENT_5,
            InstallmentType.PAYMENT_6,
            InstallmentType.PAYMENT_7,
        )
    ]

    down_payment = SafeAttributeObject(
        reservation.apartment_installments.filter(
            type=InstallmentType.DOWN_PAYMENT
        ).first()
    )

    def hitas_price(cents: Union[int, None]) -> Union[PDFCurrencyField, None]:
        if cents is None:
            return None
        return PDFCurrencyField(
            prefix=num2words(Decimal(cents) / 100, lang="fi") + " ",
            cents=cents,
            suffix=" €",
        )

    project_installment_templates = list(
        ProjectInstallmentTemplate.objects.filter(project_uuid=apartment.project_uuid)
    )

    def get_percentage(apartment_installment):
        installment_template = next(
            (
                i
                for i in project_installment_templates
                if i.type == apartment_installment.type
            ),
            None,
        )
        if (
            installment_template
            and installment_template.unit == InstallmentUnit.PERCENT
        ):
            return remove_exponent(installment_template.value)
        else:
            return None

    pdf_data = HitasContractPDFData(
        occupant_1=primary_profile.full_name,
        occupant_1_address=(
            (primary_profile.street_address or "")
            + ", "
            + (primary_profile.postal_code or "")
            + " "
            + (primary_profile.city or "")
        ).strip(),
        occupant_1_phone_number=primary_profile.phone_number,
        occupant_1_email=primary_profile.email,
        occupant_1_ssn_or_business_id=primary_profile.national_identification_number,
        occupant_2=secondary_profile.full_name,
        occupant_2_address=(
            (secondary_profile.street_address or "")
            + ", "
            + (secondary_profile.postal_code or "")
            + " "
            + (secondary_profile.city or "")
        ).strip(),
        occupant_2_phone_number=secondary_profile.phone_number,
        occupant_2_email=secondary_profile.email,
        occupant_2_ssn_or_business_id=secondary_profile.national_identification_number,
        project_housing_company=apartment.project_housing_company,
        project_contract_business_id=apartment.project_contract_business_id,
        project_address="  ".join(
            [
                apartment.project_street_address,
                f"{apartment.project_postal_code} {apartment.project_city}",
            ]
        ),
        project_realty_id=apartment.project_realty_id,
        housing_type_ownership=False,
        housing_type_rental=True,
        housing_shares=apartment.housing_shares,
        apartment_street_address=apartment.apartment_address,
        apartment_structure=apartment.apartment_structure,
        apartment_number=apartment.apartment_number,
        floor=apartment.floor,
        living_area=apartment.living_area,
        other_space=None,
        other_space_area=None,
        project_contract_transfer_restriction_false=apartment.project_contract_transfer_restriction  # noqa E501
        is False,
        project_contract_transfer_restriction_true=apartment.project_contract_transfer_restriction,  # noqa E501
        project_contract_material_selection_later_false=apartment.project_contract_material_selection_later  # noqa E501
        is False,
        project_contract_material_selection_later_true=apartment.project_contract_material_selection_later,  # noqa E501
        project_contract_material_selection_description=apartment.project_contract_material_selection_description,  # noqa E501
        sales_price=hitas_price(apartment.sales_price),
        loan_share=hitas_price(apartment.loan_share),
        debt_free_sales_price=hitas_price(apartment.debt_free_sales_price),
        payment_1_label=payment_1.type,
        payment_1_amount=PDFCurrencyField(euros=payment_1.value),
        payment_1_due_date=payment_1.due_date,
        payment_1_percentage=get_percentage(payment_1),
        payment_2_label=payment_2.type,
        payment_2_amount=PDFCurrencyField(euros=payment_2.value),
        payment_2_due_date=payment_2.due_date,
        payment_2_percentage=get_percentage(payment_2),
        payment_3_label=payment_3.type,
        payment_3_amount=PDFCurrencyField(euros=payment_3.value),
        payment_3_due_date=payment_3.due_date,
        payment_3_percentage=get_percentage(payment_3),
        payment_4_label=payment_4.type,
        payment_4_amount=PDFCurrencyField(euros=payment_4.value),
        payment_4_due_date=payment_4.due_date,
        payment_4_percentage=get_percentage(payment_4),
        payment_5_label=payment_5.type,
        payment_5_amount=PDFCurrencyField(euros=payment_5.value),
        payment_5_due_date=payment_5.due_date,
        payment_5_percentage=get_percentage(payment_5),
        payment_6_amount=PDFCurrencyField(euros=payment_6.value),
        payment_6_due_date=payment_6.due_date,
        payment_6_percentage=get_percentage(payment_6),
        payment_7_amount=PDFCurrencyField(euros=payment_7.value),
        payment_7_due_date=payment_7.due_date,
        payment_7_percentage=get_percentage(payment_7),
        second_last_payment_basis_sales_price=False,
        second_last_payment_basis_debt_free_sales_price=True,
        last_payment_basis_sales_price=False,
        last_payment_basis_debt_free_sales_price=True,
        payment_bank_1=apartment.project_contract_rs_bank,
        payment_account_number_1=apartment.project_regular_bank_account,
        payment_bank_2=apartment.project_contract_rs_bank,
        payment_account_number_2=apartment.project_barred_bank_account,
        down_payment_amount=PDFCurrencyField(
            euros=down_payment.amount if down_payment.amount else Decimal(0),
            suffix=" €",
        ),
        project_contract_apartment_completion_selection_1=apartment.project_contract_apartment_completion_selection_1,  # noqa E501
        project_contract_apartment_completion_selection_1_date=apartment.project_contract_apartment_completion_selection_1_date,  # noqa E501
        project_contract_apartment_completion_selection_2=apartment.project_contract_apartment_completion_selection_2,  # noqa E501
        project_contract_apartment_completion_selection_2_start=apartment.project_contract_apartment_completion_selection_2_start,  # noqa E501
        project_contract_apartment_completion_selection_2_end=apartment.project_contract_apartment_completion_selection_2_end,  # noqa E501
        project_contract_apartment_completion_selection_3=apartment.project_contract_apartment_completion_selection_3,  # noqa E501
        project_contract_apartment_completion_selection_3_date=apartment.project_contract_apartment_completion_selection_3_date,  # noqa E501
        project_contract_depositary=apartment.project_contract_depositary,
        project_contract_repository=apartment.project_contract_repository,
        breach_of_contract_option_1=False,
        breach_of_contract_option_2=True,
        project_contract_collateral_type=apartment.project_contract_collateral_type,
        project_contract_collateral_bank_and_address="  ".join(
            [
                apartment.project_contract_depositary or "",
                apartment.project_contract_repository or "",
            ]
        ),
        project_contract_default_collateral=apartment.project_contract_default_collateral,  # noqa E501
        project_contract_construction_permit_requested=datetime.fromisoformat(
            apartment.project_contract_construction_permit_requested
        )
        if apartment.project_contract_construction_permit_requested
        else None,
        project_contract_other_terms=apartment.project_contract_other_terms,
        project_documents_delivered=apartment.project_documents_delivered,
        signing_place_and_time="Helsingin kaupunki",
        signing_text="Kauppakirja oikeaksi todistetaan",
        salesperson=None,
    )

    return create_pdf(HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME, pdf_data)
