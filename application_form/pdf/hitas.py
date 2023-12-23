import dataclasses
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import ClassVar, Dict, Union

from num2words import num2words

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
    occupant_1_share_of_ownership: Union[str, None]
    occupant_1_address: str
    occupant_1_phone_number: str
    occupant_1_email: str
    occupant_1_ssn_or_business_id: Union[str, None]
    occupant_2: Union[str, None]
    occupant_2_share_of_ownership: Union[str, None]
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
    project_contract_material_selection_date: Union[date, None]

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
    payment_6_label: Union[str, None]
    payment_6_amount: Union[PDFCurrencyField, None]
    payment_6_due_date: Union[date, None]
    payment_6_percentage: Union[Decimal, None]
    payment_7_label: Union[str, None]
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
    salesperson: Union[str, None]
    signing_buyers: str
    sign_project_contract_depositary: Union[str, None]

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "occupant_1": "P1Ostaja1Nimi",
        "occupant_1_share_of_ownership": "P1Ostaja1Omistusosuus",
        "occupant_1_address": "P1Ostaja1Osoite",
        "occupant_1_phone_number": "P1Ostaja1Puhelin",
        "occupant_1_email": "P1Ostaja1Sähköposti",
        "occupant_1_ssn_or_business_id": "P1Ostaja1HenkariTaiY",
        "occupant_2": "P1Ostaja2Nimi",
        "occupant_2_share_of_ownership": "P1Ostaja2Omistusosuus",
        "occupant_2_address": "P1Ostaja2Osoite",
        "occupant_2_phone_number": "P1Ostaja2Puhelin",
        "occupant_2_email": "P1Ostaja2Sähköposti",
        "occupant_2_ssn_or_business_id": "P1Ostaja2HenkariTaiY",
        "apartment_number": "P2AsunnonNumero",
        "project_housing_company": "P2YhtiönToiminimi",
        "project_contract_business_id": "P2Ytunnus",
        "project_address": "P2YhtiönOsoite",
        "project_realty_id": "P2Kiinteistötunnus",
        "housing_type_ownership": "P2omistus",
        "housing_type_rental": "P2vuokra",
        "housing_shares": "P2Osakkeet",
        "apartment_street_address": "P2AsunnonOsoite",
        "floor": "P2AsunnonKerros",
        "apartment_structure": "P2Huoneistotyyppi",
        "living_area": "P2Pintaala",
        "other_space": "P2MuutTilat",
        "other_space_area": "P2MuutTilatPintaala",
        "project_contract_transfer_restriction_false": "P2EiRajoitettu",
        "project_contract_transfer_restriction_true": "P2Rajoitettu",
        "project_contract_transfer_restriction_text": "P2Rajoitus",  # UNUSED
        "project_contract_material_selection_later_false": "P2EiValintaTäsmennyksiä",
        "project_contract_material_selection_later_true": "P2ValintaTäsmennyksiäMyöhemmin",  # noqa E501
        "project_contract_material_selection_description": "P2TäsmennysOsat",
        "project_contract_material_selection_date": "P2TäsmennysAjankohta",
        "sales_price": "P3Kauppahinta",
        "loan_share": "P3OsuusYhtiönLainoista",
        "debt_free_sales_price": "P3VelatonHinta",
        "payment_1_label": "P3Erä1Nro",
        "payment_2_label": "P3Erä2Nro",
        "payment_3_label": "P3Erä3Nro",
        "payment_4_label": "P3Erä4Nro",
        "payment_5_label": "P3Erä5Nro",
        "payment_6_label": "P3Erä6Nro",
        "payment_7_label": "P3Erä7Nro",
        "payment_1_amount": "P3Erä1EUR",
        "payment_2_amount": "P3Erä2EUR",
        "payment_3_amount": "P3Erä3EUR",
        "payment_4_amount": "P3Erä4EUR",
        "payment_5_amount": "P3Erä5EUR",
        "payment_6_amount": "P3Erä6EUR",
        "payment_7_amount": "P3Erä7EUR",
        "payment_1_due_date": "P3Erä1pvm",
        "payment_2_due_date": "P3Erä2pvm",
        "payment_3_due_date": "P3Erä3pvm",
        "payment_4_due_date": "P3Erä4pvm",
        "payment_5_due_date": "P3Erä5pvm",
        "payment_6_due_date": "P3Erä6pvm",
        "payment_7_due_date": "P3Erä8pvm",  # NOTE: typo in the template
        "payment_1_percentage": "P3Erä1Pcnt",
        "payment_2_percentage": "P3Erä2Pcnt",
        "payment_3_percentage": "P3Erä3Pcnt",
        "payment_4_percentage": "P3Erä4Pcnt",  # NOTE: MISSING from template
        "payment_5_percentage": "P3Erä5Pcnt",
        "payment_6_percentage": "P3Erä6Pcnt",
        "payment_7_percentage": "P3Erä7Pcnt",
        "second_last_payment_label": "P3ToiseksiViimeinenErä",  # UNUSED
        "second_last_payment_basis_sales_price": "P3TVE008xKh",
        "second_last_payment_sp_percentage": "P3TVEPcntKh",  # UNUSED
        "second_last_payment_sp_amount": "P3TVEEurKh",  # UNUSED
        "second_last_payment_basis_debt_free_sales_price": "P3TVE0056xVh",
        "second_last_payment_dfsp_percentage": "P3TVEPcntVh",  # UNUSED
        "second_last_payment_dfsp_amount": "P3TVEEurVh",  # UNUSED
        "second_last_payment_comment": "P3TVEEräpäiväIlmoitusKommentti",  # UNUSED
        "last_payment_label": "P3ViimeinenErä",  # UNUSED
        "last_payment_basis_sales_price": "P3VE002xKh",
        "last_payment_sp_percentage": "P3VEPcntKh",  # UNUSED
        "last_payment_sp_amount": "P3VEEurKh",  # UNUSED
        "last_payment_basis_debt_free_sales_price": "P3VE0014xVh",
        "last_payment_dfsp_percentage": "P3VEPcntVh",  # UNUSED
        "last_payment_dfsp_amount": "P3VEEurVh",  # UNUSED
        "last_payment_comment": "P3VEEräpäiväIlmotusKommentti",  # UNUSED
        "payment_bank_1_payment_labels": "P3TililleMaksettavatErät",  # UNUSED
        "payment_bank_1": "P3Pankki",
        "payment_account_number_1": "P3Tilinumero",
        "payment_bank_2": "P3ViimeisinEränPankki",
        "payment_account_number_2": "P3ViimeisenEränTilinumero",
        "down_payment_amount": "P3Käsiraha",
        "project_contract_apartment_completion_selection_1": "P5ValmistuminenKiinteä",
        "project_contract_apartment_completion_selection_1_date": "P5ValmistumisPäivä",
        "project_contract_apartment_completion_selection_2": "P5ValmistuminenAikaväli",
        "project_contract_apartment_completion_selection_2_start": "P5ValmistusAikaisintaan",  # noqa E501
        "project_contract_apartment_completion_selection_2_end": "P5ValmistusViimeistään",  # noqa E501
        "project_contract_apartment_completion_selection_3": "P5ValmistuminenTapahtunut",  # noqa E501
        "project_contract_apartment_completion_selection_3_date": "P5ValmistumisenKommentti",  # noqa E501
        "project_contract_depositary": "P9TurvaAsiankirjaSäilyttäjä",
        "project_contract_repository": "P9TurvaAsiankirjaSäilysOsoite",
        "breach_of_contract_option_1": "P15SopimusRikkomisestaVahinkoKorvaus",
        "breach_of_contract_option_2": "P15SopimusRikkomisestaKulutJa2PcntVH",
        "project_contract_collateral_type": "vakuuden laji",  # FIXME: where to?
        "project_contract_collateral_bank_and_address": "P17AKL217vakuus",  # Correct?
        "project_contract_default_collateral": "P17AKL219suorituskyvyttymyysvakuus",
        "project_contract_construction_permit_requested": "P19RakennuslupaTietoa",
        "project_contract_other_terms": "P22MuutEhdotOsa1",
        "project_contract_other_terms_2": "P22MuutEhdotOsa2",  # UNUSED
        "project_documents_delivered": "P22LuovutetutAsiakirjat",
        "signing_place_and_time": "AllekirjoitusPaikkaJaAika",
        "salesperson": "AllekirjoitusValtakirjalla",
        "signing_buyers": "AllekirjoitusOstajat",
        "collateral_place_and_time": "AKL17VakuuksienAsetusPaikkaJaAika",  # UNUSED
        "sign_project_contract_depositary": "TurvaAsiakirjojenSäilyttäjä",  # UNUSED
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
        occupant_1_share_of_ownership=None,
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
        occupant_2_share_of_ownership=None,
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
        project_contract_material_selection_date=apartment.project_contract_material_selection_date,  # noqa E501
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
        payment_6_label=payment_6.type,
        payment_6_percentage=get_percentage(payment_6),
        payment_6_amount=PDFCurrencyField(euros=payment_6.value),
        payment_6_due_date=payment_6.due_date,
        payment_7_label=payment_7.type,
        payment_7_percentage=get_percentage(payment_7),
        payment_7_amount=PDFCurrencyField(euros=payment_7.value),
        payment_7_due_date=payment_7.due_date,
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
        project_contract_construction_permit_requested=(
            apartment.project_contract_construction_permit_requested
        )
        if apartment.project_contract_construction_permit_requested
        else None,
        project_contract_other_terms=apartment.project_contract_combined_terms,
        project_documents_delivered=apartment.project_documents_delivered,
        signing_place_and_time="Helsinki",
        salesperson=apartment.project_acc_salesperson,
        signing_buyers=" & ".join(
            name
            for name in [primary_profile.full_name, secondary_profile.full_name]
            if name
        ),
        sign_project_contract_depositary=apartment.project_contract_depositary,
    )
    return create_hitas_contract_pdf_from_data(pdf_data)


def create_hitas_contract_pdf_from_data(pdf_data: HitasContractPDFData) -> BytesIO:
    return create_pdf(HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME, pdf_data)
