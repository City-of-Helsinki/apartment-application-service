import dataclasses
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import ClassVar, Dict, Optional, Union

from django.utils import timezone

from apartment.elastic.queries import get_apartment
from apartment_application_service.pdf import create_pdf, PDFCurrencyField, PDFData
from apartment_application_service.utils import SafeAttributeObject
from application_form.models import ApartmentReservation
from invoicing.enums import InstallmentType
from users.models import User

HASO_CONTRACT_PDF_TEMPLATE_FILE_NAME = "haso_contract_template.pdf"
HASO_RELEASE_PDF_TEMPLATE_FILE_NAME = "haso_release_template.pdf"


@dataclasses.dataclass
class HasoContractPDFData(PDFData):
    alterations: Union[str, None]
    apartment_number: Union[str, None]
    apartment_structure: Union[str, None]
    approver: str
    approval_date: Union[str, None]
    floor: Union[int, None]
    index_increment: Union[Decimal, None]
    installment_amount: Union[PDFCurrencyField, None]
    living_area: Union[float, None]
    occupant_1: str
    occupant_1_signing_text: str
    occupant_1_email: str
    occupant_1_phone_number: str
    occupant_1_ssn: str
    occupant_1_street_address: str
    occupant_2: Union[str, None]
    occupant_2_signing_text: str
    occupant_2_email: Union[str, None]
    occupant_2_phone_number: Union[str, None]
    occupant_2_ssn: Union[str, None]
    occupant_2_street_address: Union[str, None]
    payment_due_date: Union[date, None]
    project_acc_salesperson: Union[str, None]
    project_contract_apartment_completion: Union[str, None]
    project_contract_other_terms: Union[str, None]
    project_contract_right_of_occupancy_payment_verification: Union[str, None]
    project_contract_usage_fees: Union[str, None]
    project_housing_company: Union[str, None]
    project_street_address: Union[str, None]
    right_of_occupancy_fee: Union[PDFCurrencyField, None]
    right_of_occupancy_fee_m2: Union[PDFCurrencyField, None]
    right_of_occupancy_payment: Union[PDFCurrencyField, None]
    right_of_residence_number: Union[str, None]
    signing_place_and_time: str

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "alterations": "P31Muutostyöt",
        "approver": "P1AOhyväksyjä",
        "apartment_number": "P2AOHuoneistoNumero",
        "apartment_structure": "P2Huoneluku",
        "approval_date": "P1Hyväksymispäivä",
        "floor": "P2HuoneistoKerros",
        "index_increment": "P31Indeksikorotus",
        "installment_amount": "P31Maksuerä1suuruus",
        "living_area": "P2HuoneistoPintaala",
        "occupant_1": "P1AOhaltija1nimi",
        "occupant_1_signing_text": "AllekirjoitusAOhaltija1",
        "occupant_1_email": "P1Sähköposti1",
        "occupant_1_phone_number": "P1Puhelin1",
        "occupant_1_ssn": "P1Henkilötunnus1",
        "occupant_1_street_address": "P1Osoite1",
        "occupant_2": "P1AOhaltija2nimi",
        "occupant_2_signing_text": "AllekirjoitusAOhaltija2",
        "occupant_2_email": "P1Sähköposti2",
        "occupant_2_phone_number": "P1Puhelin2",
        "occupant_2_ssn": "P1Henkilötunnus2",
        "occupant_2_street_address": "P1Osoite2",
        "payment_due_date": "P31Eräpäivä1",
        "project_acc_salesperson": "AllekirjoitusValtakirjalla",
        "project_contract_apartment_completion": "P6LuovutusPäivämäärä",
        "project_contract_other_terms": "P91MuutEhdotJaAsiakirjat",
        "project_contract_right_of_occupancy_payment_verification": (
            "P9RakentamisAOmaksunTarkistus"
        ),
        "project_contract_usage_fees": "P4AOhaltijoidenLisäkorvaukset",
        "project_housing_company": "P2AOkohteenNimi",
        "project_street_address": "P2AOkohteenOsoite",
        "right_of_occupancy_fee": "P4EuroKK",
        "right_of_occupancy_fee_m2": "P4m2KK",
        "right_of_occupancy_payment": "P31TalonRakentamisAOmaksu",
        "right_of_residence_number": "P1Järjestysnumero",
        "signing_place_and_time": "AllekirjoitusPaikkaAika",
    }


@dataclasses.dataclass
class HasoReleasePDFData(PDFData):
    project_housing_company: Optional[str]
    project_street_address: Optional[str]
    project_completion_date: Optional[date]
    apartment_number: Optional[str]
    occupant_names: Optional[str]
    occupant_phone_numbers: Optional[str]
    right_of_residence_number: Optional[str]
    release_date: date
    original_right_of_occupancy_payment: PDFCurrencyField
    payment_1_date: date
    payment_1_cost_index: Decimal
    release_date_cost_index: Decimal
    adjusted_right_of_occupancy_payment: PDFCurrencyField
    alteration_work: PDFCurrencyField
    refund: Optional[PDFCurrencyField]
    release_payment: PDFCurrencyField
    document_date: date
    sales_person_name: str

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "project_housing_company": "Kohde",
        "project_street_address": "Kohteen osoite",
        "project_completion_date": "Kohteen valmistumisaika",
        "apartment_number": "Huoneisto",
        "occupant_names": "Asumisoikeuden haltijat",
        "occupant_phone_numbers": "Puhelinnumerot",
        "right_of_residence_number": "Järjestysnumero",
        "release_date": "Luopumispäivä",
        "original_right_of_occupancy_payment": "Alkuperäinen asumisoikeusmaksu",
        "payment_1_date": "Ensimmäinen maksupäivä",
        "payment_1_cost_index": "Maksupäivän indeksi",
        "release_date_cost_index": "Luopumispäivän indeksi",
        "adjusted_right_of_occupancy_payment": "Indeksikorotettu asumisoikeusmaksu",
        "alteration_work": "Muutostyöt",
        "refund": "Hyvitettävä",
        "release_payment": "Luovutushinta asomaksuindmuutostyöt",
        "document_date": "Päivämäärä",
        "sales_person_name": "Myyjä",
    }


def create_haso_contract_pdf(
    reservation: ApartmentReservation,
    sales_price_paid_place: str,
    sales_price_paid_time: str,
    salesperson: User,
) -> BytesIO:
    pdf_data = get_haso_contract_pdf_data(
        reservation,
        sales_price_paid_place,
        sales_price_paid_time,
        salesperson,
    )
    return create_haso_contract_pdf_from_data(pdf_data)


def get_haso_contract_pdf_data(
    reservation: ApartmentReservation,
    sales_price_paid_place: str,
    sales_price_paid_time: str,
    salesperson: User,
) -> HasoContractPDFData:
    customer = SafeAttributeObject(reservation.customer)
    primary_profile = SafeAttributeObject(customer.primary_profile)
    secondary_profile = SafeAttributeObject(customer.secondary_profile)
    apartment = get_apartment(reservation.apartment_uuid, include_project_fields=True)

    first_payment = SafeAttributeObject(
        reservation.apartment_installments.filter(
            type=InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT
        ).first()
    )

    completion_start = apartment.project_contract_estimated_handover_date_start
    completion_start_str = (
        completion_start.strftime("%-d.%-m.%Y") if completion_start else ""
    )
    completion_end = apartment.project_contract_estimated_handover_date_end
    completion_end_str = completion_end.strftime("%-d.%-m.%Y") if completion_end else ""

    right_of_occupancy_fee_m2_euros = (
        Decimal(apartment.right_of_occupancy_fee / 100.0 / apartment.living_area)
        if apartment.right_of_occupancy_fee is not None
        else None
    )

    pdf_data = HasoContractPDFData(
        occupant_1=primary_profile.full_name,
        occupant_1_signing_text=primary_profile.full_name,
        occupant_1_street_address=(
            (primary_profile.street_address or "")
            + ", "
            + (primary_profile.postal_code or "")
            + " "
            + (primary_profile.city or "")
        ).strip(),
        occupant_1_phone_number=primary_profile.phone_number,
        occupant_1_email=primary_profile.email,
        occupant_1_ssn=primary_profile.national_identification_number,
        occupant_2=secondary_profile.full_name,
        occupant_2_signing_text=secondary_profile.full_name,
        occupant_2_street_address=(
            (secondary_profile.street_address or "")
            + ", "
            + (secondary_profile.postal_code or "")
            + " "
            + (secondary_profile.city or "")
        ).strip(),
        occupant_2_phone_number=secondary_profile.phone_number,
        occupant_2_email=secondary_profile.email,
        occupant_2_ssn=secondary_profile.national_identification_number,
        right_of_residence_number=reservation.right_of_residence,
        project_housing_company=apartment.project_housing_company,
        project_street_address=apartment.project_street_address,
        apartment_number=apartment.apartment_number,
        apartment_structure=apartment.apartment_structure,
        living_area=apartment.living_area,
        floor=apartment.floor,
        right_of_occupancy_payment=PDFCurrencyField(
            cents=apartment.current_right_of_occupancy_payment, suffix=" €"
        ),
        payment_due_date=first_payment.due_date,
        installment_amount=PDFCurrencyField(euros=first_payment.value),
        right_of_occupancy_fee=PDFCurrencyField(
            cents=apartment.right_of_occupancy_fee, suffix=" € / kk"
        ),
        right_of_occupancy_fee_m2=PDFCurrencyField(
            euros=right_of_occupancy_fee_m2_euros, suffix=" € /m²/kk"
        ),
        project_contract_apartment_completion=(
            f"{completion_start_str} — {completion_end_str}"
            if completion_start_str or completion_end_str
            else ""
        ),
        signing_place_and_time=f"{sales_price_paid_place} {sales_price_paid_time}",  # noqa: E501
        project_acc_salesperson=salesperson.full_name,
        project_contract_other_terms=apartment.project_contract_combined_terms,
        project_contract_usage_fees=apartment.project_contract_usage_fees,
        project_contract_right_of_occupancy_payment_verification=(
            apartment.project_contract_right_of_occupancy_payment_verification
        ),
        approver="Helsingin kaupunki",
        # TODO the following fields are still WIP
        approval_date=None,
        alterations=None,
        index_increment=None,
    )
    return pdf_data


def create_haso_contract_pdf_from_data(pdf_data: HasoContractPDFData) -> BytesIO:
    return create_pdf(HASO_CONTRACT_PDF_TEMPLATE_FILE_NAME, pdf_data)


def create_haso_release_pdf(
    sales_person_name: str, reservation: ApartmentReservation
) -> BytesIO:
    pdf_data = get_haso_release_pdf_data(sales_person_name, reservation)
    return create_haso_release_pdf_from_data(pdf_data)


def get_haso_release_pdf_data(
    sales_person_name: str, reservation: ApartmentReservation
) -> HasoReleasePDFData:
    customer = SafeAttributeObject(reservation.customer)
    primary_profile = SafeAttributeObject(customer.primary_profile)
    secondary_profile = SafeAttributeObject(customer.secondary_profile)
    apartment = get_apartment(reservation.apartment_uuid, include_project_fields=True)

    revaluation = reservation.revaluation

    pdf_data = HasoReleasePDFData(
        project_housing_company=apartment.project_housing_company,
        project_street_address=apartment.project_street_address,
        apartment_number=apartment.apartment_number,
        project_completion_date=apartment.project_completion_date,
        occupant_names=", ".join(
            filter(None, (primary_profile.full_name, secondary_profile.full_name))
        ),
        occupant_phone_numbers=", ".join(
            filter(None, (primary_profile.phone_number, secondary_profile.phone_number))
        ),
        right_of_residence_number=reservation.right_of_residence,
        release_date=revaluation.end_date,
        original_right_of_occupancy_payment=PDFCurrencyField(
            euros=revaluation.start_right_of_occupancy_payment
        ),
        payment_1_date=revaluation.start_date,
        payment_1_cost_index=revaluation.start_cost_index_value,
        release_date_cost_index=revaluation.end_cost_index_value,
        adjusted_right_of_occupancy_payment=PDFCurrencyField(
            euros=revaluation.end_right_of_occupancy_payment
        ),
        alteration_work=PDFCurrencyField(euros=revaluation.alteration_work),
        refund=PDFCurrencyField(euros=revaluation.alteration_work),
        release_payment=PDFCurrencyField(
            euros=revaluation.end_right_of_occupancy_payment
            + revaluation.alteration_work
        ),
        document_date=timezone.now().date(),
        sales_person_name=sales_person_name,
    )
    return pdf_data


def create_haso_release_pdf_from_data(pdf_data: HasoReleasePDFData) -> BytesIO:
    return create_pdf(HASO_RELEASE_PDF_TEMPLATE_FILE_NAME, pdf_data)
