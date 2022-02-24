import dataclasses
from datetime import date
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from functools import lru_cache
from typing import ClassVar, Dict
from uuid import UUID

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartment, get_projects
from apartment_application_service.pdf import create_pdf, PDFData

INVOICE_PDF_TEMPLATE_FILE_NAME = "invoice_template.pdf"


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


def create_invoice_pdf_from_installments(installments):
    @lru_cache
    def get_cached_project(project_uuid: UUID):
        return get_projects(project_uuid)[0]

    @lru_cache
    def get_cached_apartment(apartment_uuid: UUID) -> ApartmentDocument:
        return get_apartment(apartment_uuid)

    invoice_pdf_data_list = []
    for installment in installments:
        reservation = installment.apartment_reservation
        profile = reservation.application_apartment.application.customer.primary_profile
        apartment = get_cached_apartment(reservation.apartment_uuid)
        project = get_cached_project(apartment.project_uuid)
        invoice_pdf_data = InvoicePDFData(
            recipient=project.project_housing_company,
            recipient_account_number=installment.account_number,
            payer_name_and_address=f"{profile.first_name} {profile.last_name}\n\n"
            f"{profile.street_address}\n"
            f"{profile.postal_code} {profile.city}",
            reference_number=installment.reference_number,
            due_date=installment.due_date,
            amount=installment.value,
            apartment=_("Apartment") + f" {apartment.apartment_number}\n\n"
            f"{installment.type}"
            + 20 * " "
            + str(installment.value).replace(".", ",")
            + " €",
        )
        invoice_pdf_data_list.append(invoice_pdf_data)
    return create_pdf(INVOICE_PDF_TEMPLATE_FILE_NAME, invoice_pdf_data_list)
