from django.conf import settings
from xml.etree import ElementTree

from invoicing.models import ApartmentInstallment
from invoicing.sap.utils import get_installment_type_text


def assert_apartment_installment_match_xml_data(
    apartment_installment: ApartmentInstallment, xml_content: str
):
    assert xml_content

    root_element = ElementTree.fromstring(xml_content)
    assert root_element

    accounts_receivable = root_element.find("SBO_AccountsReceivable")
    assert accounts_receivable

    sender_id = accounts_receivable.find("SenderId")
    assert sender_id is not None
    assert sender_id.text == settings.SAP["SENDER_ID"]

    company_code = accounts_receivable.find("CompanyCode")
    assert company_code is not None
    assert company_code.text == settings.SAP["COMPANY_CODE"]

    document_type = accounts_receivable.find("DocumentType")
    assert document_type is not None
    assert document_type.text == settings.SAP["DOCUMENT_TYPE"]

    document_date = accounts_receivable.find("DocumentDate")
    assert document_date is not None
    assert document_date.text

    posting_date = accounts_receivable.find("PostingDate")
    assert posting_date is not None
    assert posting_date.text

    reference = accounts_receivable.find("Reference")
    assert reference is not None
    assert reference.text == apartment_installment.reference_number

    expected_reference_document_number = (
        f"{settings.SAP.get('COMPANY_CODE')}"
        f"{settings.SAP.get('DOCUMENT_TYPE')}"
        f"{settings.SAP.get('SENDER_ID')[-3:]}"
        f"{document_date.text[2:4]}"
        f"{apartment_installment.invoice_number.zfill(9)}"
    )
    reference_document_number = accounts_receivable.find("ReferenceDocumentNumber")
    assert reference_document_number is not None
    assert reference_document_number.text == expected_reference_document_number

    header_text = accounts_receivable.find("HeaderText")
    assert header_text is not None
    assert header_text.text == get_installment_type_text(apartment_installment.type)

    currency_code = accounts_receivable.find("CurrencyCode")
    assert currency_code is not None
    assert currency_code.text == settings.SAP["CURRENCY_CODE"]

    line_items = accounts_receivable.findall("LineItem")
    assert len(line_items) == 1
