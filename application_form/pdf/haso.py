import dataclasses
from datetime import date
from decimal import Decimal
from django.utils import timezone
from io import BytesIO
from num2words import num2words
from typing import ClassVar, Dict, Optional, Union

from apartment.elastic.queries import get_apartment
from apartment_application_service.pdf import create_pdf, PDFCurrencyField, PDFData
from apartment_application_service.utils import SafeAttributeObject
from application_form.models import ApartmentReservation
from invoicing.enums import InstallmentType

HASO_CONTRACT_PDF_TEMPLATE_FILE_NAME = "haso_contract_template.pdf"
HASO_RELEASE_PDF_TEMPLATE_FILE_NAME = "haso_release_template.pdf"


@dataclasses.dataclass
class HasoContractPDFData(PDFData):
    alterations: Union[str, None]
    apartment_number: Union[str, None]
    apartment_structure: Union[str, None]
    approval_date: Union[str, None]
    floor: Union[int, None]
    index_increment: Union[Decimal, None]
    installment_amount: Union[PDFCurrencyField, None]
    living_area: Union[str, None]
    occupant_1: str
    occupant_1_email: str
    occupant_1_phone_number: str
    occupant_1_ssn: str
    occupant_1_street_address: str
    occupant_2: Union[str, None]
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
    right_of_occupancy_payment_text: Union[str, None]
    right_of_residence_number: Union[str, None]
    signing_place: str
    signing_text: str
    signing_time: Union[str, None]

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "alterations": "Muutostyöt",
        "apartment_number": "Huoneiston numero",
        "apartment_structure": "Huoneistotyyppi",
        "approval_date": "Hyväksymispäivämäärä",
        "floor": "Sijaintikerros",
        "index_increment": "Indeksikorotus",
        "installment_amount": "Maksuerän suuruus",
        "living_area": "Huoneiston pinta-ala",
        "occupant_1": "Asumisoikeuden haltija 1",
        "occupant_1_email": "Haltija 1 sähköposti",
        "occupant_1_phone_number": "Haltija 1 puhelinnumero",
        "occupant_1_ssn": "Haltija 1 henkilötunnus",
        "occupant_1_street_address": "Haltija 1 osoite",
        "occupant_2": "Asumisoikeuden haltija 2",
        "occupant_2_email": "Haltija 2 sähköposti",
        "occupant_2_phone_number": "Haltija 2 puhelinnumero",
        "occupant_2_ssn": "Haltija 2 henkilötunnus",
        "occupant_2_street_address": "Haltija 2 osoite",
        "payment_due_date": "Eräpäivä maksulle",
        "project_acc_salesperson": "rakennuttaja-asimies",
        "project_contract_apartment_completion": "Valmistumisaika",
        "project_contract_other_terms": "Muut ehdot",
        "project_contract_right_of_occupancy_payment_verification": "Lisätietokenttä",
        "project_contract_usage_fees": "Vapaakenttä käyttövastike",
        "project_housing_company": "Kohteen nimi",
        "project_street_address": "Kohteen osoite",
        "right_of_occupancy_fee": "Käyttövastike",
        "right_of_occupancy_fee_m2": "Käyttövastike asuinneliö",
        "right_of_occupancy_payment": "Alkuperäinen asumisoikeusmaksu",
        "right_of_occupancy_payment_text": "Alkuperäinen asumisoikeusmaksu tekstinä",
        "right_of_residence_number": "järjestysnumero",
        "signing_place": "Paikka",
        "signing_text": "Sopimus oikeaksi todistetaan",
        "signing_time": "Aika",
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


def create_haso_contract_pdf(reservation: ApartmentReservation) -> BytesIO:
    customer = SafeAttributeObject(reservation.customer)
    primary_profile = SafeAttributeObject(customer.primary_profile)
    secondary_profile = SafeAttributeObject(customer.secondary_profile)
    apartment = get_apartment(reservation.apartment_uuid, include_project_fields=True)

    first_payment = SafeAttributeObject(
        reservation.apartment_installments.filter(
            type=InstallmentType.PAYMENT_1
        ).first()
    )

    completion_start = apartment.project_contract_apartment_completion_selection_2_start
    completion_start_str = (
        completion_start.strftime("%-d.%-m.%Y") if completion_start else ""
    )
    completion_end = apartment.project_contract_apartment_completion_selection_2_end
    completion_end_str = completion_end.strftime("%-d.%-m.%Y") if completion_end else ""

    right_of_occupancy_fee_m2_euros = (
        Decimal(apartment.right_of_occupancy_fee / 100.0 / apartment.living_area)
        if apartment.right_of_occupancy_fee is not None
        else None
    )

    pdf_data = HasoContractPDFData(
        occupant_1=primary_profile.full_name,
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
        right_of_occupancy_payment_text=num2words(
            Decimal(apartment.current_right_of_occupancy_payment) / 100, lang="fi"
        )
        if apartment.current_right_of_occupancy_payment is not None
        else None,
        payment_due_date=first_payment.due_date,
        installment_amount=PDFCurrencyField(euros=first_payment.value),
        right_of_occupancy_fee=PDFCurrencyField(
            cents=apartment.right_of_occupancy_fee, suffix=" € / kk"
        ),
        right_of_occupancy_fee_m2=PDFCurrencyField(
            euros=right_of_occupancy_fee_m2_euros, suffix=" € /m\u00b2/kk"
        ),
        project_contract_apartment_completion=(
            f"{completion_start_str} — {completion_end_str}"
            if completion_start_str or completion_end_str
            else ""
        ),
        signing_place="Helsingin kaupunki",
        project_acc_salesperson=apartment.project_acc_salesperson,
        project_contract_other_terms=apartment.project_contract_other_terms,
        project_contract_usage_fees=apartment.project_contract_usage_fees,
        project_contract_right_of_occupancy_payment_verification=apartment.project_contract_right_of_occupancy_payment_verification,  # noqa E501
        # TODO the following fields are still WIP
        signing_text="Sopimus oikeaksi todistetaan",
        signing_time=None,
        approval_date=None,
        alterations=None,
        index_increment=None,
    )

    return create_pdf(HASO_CONTRACT_PDF_TEMPLATE_FILE_NAME, pdf_data)


def create_haso_release_pdf(
    sales_person_name: str, reservation: ApartmentReservation
) -> BytesIO:
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
    return create_pdf(HASO_RELEASE_PDF_TEMPLATE_FILE_NAME, pdf_data)
