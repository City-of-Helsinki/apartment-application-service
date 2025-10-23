import dataclasses
import logging
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import ClassVar, Dict, List, Union
from uuid import UUID

from django.db.models import QuerySet
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartment, get_project
from apartment.enums import OwnershipType
from apartment_application_service.pdf import create_pdf, PDFData
from customer.models import Customer
from invoicing.enums import InstallmentType
from invoicing.models import ApartmentInstallment

_logger = logging.getLogger(__name__)
INVOICE_PDF_TEMPLATE_FILE_NAME = "invoice_template.pdf"


def _get_payer_name_and_address(customer: Customer) -> str:
    primary_profile = customer.primary_profile
    payer_names = primary_profile.full_name
    if secondary_profile := customer.secondary_profile:
        payer_names = (
            f"{primary_profile.full_name} {_('and')} {secondary_profile.full_name}"
        )
    return (
        f"{payer_names}\n\n{primary_profile.street_address}\n"
        f"{primary_profile.postal_code} {primary_profile.city}"
    )


@dataclasses.dataclass
class InvoicePDFData(PDFData):
    recipient: str
    recipient_account_number: str
    payer_name_and_address: str
    reference_number: str
    due_date: date
    amount: Decimal
    apartment: str

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "recipient_account_number": "Pankki ja Iban",
        "recipient": "Saaja",
        "payer_name_and_address": "Maksajien nimi ja osoite",
        "reference_number": "Viitenumero",
        "due_date": "Eräpäivä",
        "amount": "Summa",
        "apartment": "Huoneisto",
    }

def get_invoice_pdf_data_from_installment(
        installment: ApartmentInstallment,
    ) -> InvoicePDFData:
        @lru_cache
        def get_cached_project(project_uuid: UUID):
            return get_project(project_uuid)

        @lru_cache
        def get_cached_apartment(apartment_uuid: UUID) -> ApartmentDocument:
            return get_apartment(apartment_uuid, include_project_fields=True)


        reservation = installment.apartment_reservation
        payer_name_and_address = _get_payer_name_and_address(
            installment.apartment_reservation.customer
        )
        apartment = get_cached_apartment(reservation.apartment_uuid)
        project = get_cached_project(apartment.project_uuid)

        # override language to Finnish, as the user's browser settings etc.
        # shouldn't affect the printed out PDFs
        with translation.override("fi"):
            apartment_text = (
                _("Apartment")
                + f" {apartment.apartment_number}\n\n{installment.type}"
                + 20 * " "
                + str(installment.value).replace(".", ",")
                + " €"
            )

        final_installment_type = InstallmentType.PAYMENT_7
        if apartment.project_ownership_type == OwnershipType.HASO.value:
            final_installment_type = InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3
            pass

        payment_recipient = apartment.project_payment_recipient
        if installment.type == final_installment_type:
            payment_recipient = apartment.project_payment_recipient_final
            pass

        invoice_pdf_data = InvoicePDFData(
            recipient=payment_recipient,
            recipient_account_number=f"{project.project_contract_rs_bank or ''} "
            f"{installment.account_number}".strip(),
            payer_name_and_address=payer_name_and_address,
            reference_number=installment.reference_number,
            due_date=installment.due_date,
            amount=installment.value,
            apartment=apartment_text,
        )

        return invoice_pdf_data

def create_invoice_pdf_from_installments(
    installments: Union[QuerySet, List[ApartmentInstallment]]
):

    invoice_pdf_data_list = []
    for installment in installments:
        invoice_pdf_data = get_invoice_pdf_data_from_installment(installment)
        invoice_pdf_data_list.append(invoice_pdf_data)

    return create_pdf(INVOICE_PDF_TEMPLATE_FILE_NAME, invoice_pdf_data_list)
