# <SBO_AccountsReceivableContainer>
#     <SBO_AccountsReceivable>
#         <SenderId>ID066</SenderId>
#         <CompanyCode>2800</CompanyCode>
#         <DocumentType>5R</DocumentType>
#         <DocumentDate>20211207</DocumentDate>
#         <PostingDate>20211207</PostingDate>
#         <Reference>000060104</Reference>
#         <HeaderText>AO-maksu</HeaderText>
#         <CurrencyCode>EUR</CurrencyCode>
#         <!-- This LineItem and the next belong to the same payment. -->
#         <LineItem>
#             <AmountInDocumentCurrency>34700,00</AmountInDocumentCurrency>
#             <LineText>AO-maksu</LineText>
#             <CustomerID>170980-112F</CustomerID>
#             <BaseLineDate>20211207</BaseLineDate>
#             <PaymentTerms>N073</PaymentTerms>
#             <ReferenceId>73000601041</ReferenceId>
#             <InfoCustomerID>170980-112F</InfoCustomerID>
#             <InfoName1>Mattila</InfoName1>
#             <InfoName2>Maija</InfoName2>
#             <InfoName3></InfoName3>
#             <InfoName4></InfoName4>
#             <InfoAddress1>Honkaharjunkatu 6 A7</InfoAddress1>
#             <InfoCity>Kuopio</InfoCity>
#             <InfoPostalcode>70500</InfoPostalcode>
#         </LineItem>
#         <!--
#         This line item is linked to the one above.
#         This one is bookkeeping related and the minus (-)
#         sign in front of the sum is expected here since this
#         has to do with debit/credit bookkeeping.
#         -->
#         <LineItem>
#             <TaxCode>4Z</TaxCode>
#             <AmountInDocumentCurrency>-34700,00</AmountInDocumentCurrency>
#             <LineText>AO-maksu</LineText>
#             <GLAccount>350080</GLAccount>
#             <WBS_Element>282500203502303</WBS_Element>
#         </LineItem>
#     </SBO_AccountsReceivable>
#     <SBO_AccountsReceivable>
#         <SenderId>ID066</SenderId>
#         <CompanyCode>2800</CompanyCode>
#         <DocumentType>5R</DocumentType>
#         <DocumentDate>20211203</DocumentDate>
#         <PostingDate>20211203</PostingDate>
#         <Reference>000060105</Reference>
#         <HeaderText>AO-maksu</HeaderText>
#         <CurrencyCode>EUR</CurrencyCode>
#         <LineItem>
#             <AmountInDocumentCurrency>24029,35</AmountInDocumentCurrency>
#             <LineText>AO-maksu</LineText>
#             <CustomerID>110266-242J</CustomerID>
#             <BaseLineDate>20211203</BaseLineDate>
#             <PaymentTerms>N073</PaymentTerms>
#             <ReferenceId>73000601054</ReferenceId>
#             <InfoCustomerID>110266-242J</InfoCustomerID>
#             <InfoName1>Nikitina</InfoName1>
#             <InfoName2>Natalia</InfoName2>
#             <InfoName3></InfoName3>
#             <InfoName4></InfoName4>
#             <InfoAddress1>Kivikonkaari 5 B 27</InfoAddress1>
#             <InfoCity>Helsinki</InfoCity>
#             <InfoPostalcode>00940</InfoPostalcode>
#         </LineItem>
#         <LineItem>
#             <TaxCode>4Z</TaxCode>
#             <AmountInDocumentCurrency>-24029,35</AmountInDocumentCurrency>
#             <LineText>AO-maksu</LineText>
#             <GLAccount>350080</GLAccount>
#             <WBS_Element>282500203702303</WBS_Element>
#         </LineItem>
#     </SBO_AccountsReceivable>
# </SBO_AccountsReceivableContainer>
from django.conf import settings
from typing import List
from xml.etree.ElementTree import Element, SubElement

from application_form.models import ApartmentReservation
from invoicing.models import ApartmentInstallment
from invoicing.sap.utils import (
    create_reference_document_number,
    get_base_line_date_string,
    get_installment_type_text,
)


def _append_account_receivable_container_xml(
    parent: Element,
    apartment_installment: ApartmentInstallment,
) -> Element:
    sbo_account_receivable = SubElement(parent, "SBO_AccountsReceivable")

    create_at_str = apartment_installment.created_at.strftime("%Y%m%d")

    # FI: Lähettäjätunnus
    sender_id = SubElement(sbo_account_receivable, "SenderId")
    sender_id.text = settings.SAP["SENDER_ID"]

    # FI: Yritys
    company_code = SubElement(sbo_account_receivable, "CompanyCode")
    company_code.text = settings.SAP["COMPANY_CODE"]

    # FI: Tositelaji
    document_type = SubElement(sbo_account_receivable, "DocumentType")
    document_type.text = settings.SAP["DOCUMENT_TYPE"]

    # FI: Tositteen päivämäärä
    document_date = SubElement(sbo_account_receivable, "DocumentDate")
    document_date.text = create_at_str

    # FI: Tositteen kirjauspäivämäärä
    posting_date = SubElement(sbo_account_receivable, "PostingDate")
    posting_date.text = create_at_str

    # FI: Viitetositenumero
    reference_document_number = SubElement(
        sbo_account_receivable, "ReferenceDocumentNumber"
    )
    reference_document_number.text = create_reference_document_number(
        apartment_installment.created_at, apartment_installment.invoice_number
    )

    # FI: Viite
    reference = SubElement(sbo_account_receivable, "Reference")
    reference.text = apartment_installment.reference_number

    # FI: Tositteen otsikkoteksti
    header_text = SubElement(sbo_account_receivable, "HeaderText")
    header_text.text = get_installment_type_text(apartment_installment.type)

    # FI: Valuutta-avain
    currency_code = SubElement(sbo_account_receivable, "CurrencyCode")
    currency_code.text = settings.SAP["CURRENCY_CODE"]

    # Line information
    line_item = SubElement(sbo_account_receivable, "LineItem")

    # FI: Arvonlisäverotunnus
    tax_code = SubElement(line_item, "TaxCode")
    tax_code.text = settings.SAP["TAX_CODE"]

    # FI: Summa tositevaluuttana
    amount_in_document_currency = SubElement(line_item, "AmountInDocumentCurrency")
    amount_in_document_currency.text = str(apartment_installment.value)

    # FI: Riviteksti
    line_text = SubElement(line_item, "LineText")
    line_text.text = header_text.text

    # FI: Pääkirjanpidon pääkirjatili
    gl_account = SubElement(line_item, "GLAccount")
    gl_account.text = settings.SAP["GL_ACCOUNT"]

    # FI: Projektirakenteen osa (PRR-osa)
    # TODO: Mikko selvittää WBS_Elementin
    wbs_element = SubElement(line_item, "WBS_Element")
    wbs_element.text = ""

    # FI: Henkilöasiakkaan HeTu
    customer_id = SubElement(line_item, "CustomerID")
    customer_id.text = (
        apartment_installment.apartment_reservation.customer.primary_profile.national_identification_number  # NOQA: E501
    )

    # FI: Eräpäivän lakennan peruspäivämäärä
    base_line_date = SubElement(line_item, "BaseLineDate")
    base_line_date.text = get_base_line_date_string(apartment_installment.due_date)

    # FI: Maksuehtoavain
    payment_terms = SubElement(line_item, "PaymentTerms")
    payment_terms.text = settings.SAP.get("PAYMENT_TERMS")

    # FI: Maksuviite
    reference_id = SubElement(line_item, "ReferenceId")
    reference_id.text = apartment_installment.reference_number

    # FI: Infotieto Henkilöasiakkaan HeTu (Kumppani)
    if apartment_installment.apartment_reservation.customer.secondary_profile:
        secondary_profile = (
            apartment_installment.apartment_reservation.customer.secondary_profile
        )

        # FI: Infotieto henkilöasiakkaan HeTu
        info_customer_id = SubElement(line_item, "InfoCustomerID")
        info_customer_id.text = (
            secondary_profile.national_identification_number  # NOQA: E501
        )

        # FI: Infotieto nimi rivi 1
        info_name_1 = SubElement(line_item, "InfoName1")
        info_name_1.text = secondary_profile.first_name

        # FI: Infotieto nimi rivi 2
        info_name_2 = SubElement(line_item, "InfoName2")
        info_name_2.text = secondary_profile.last_name

        # FI: Infotieto osoite rivi 1
        info_address_1 = SubElement(line_item, "InfoAddress1")
        info_address_1.text = secondary_profile.street_address

        # FI: Infotieto paikkakunta
        info_city = SubElement(line_item, "InfoCity")
        info_city.text = secondary_profile.city

        # FI: Infotieto postinumero
        info_city = SubElement(line_item, "InfoPostalcode")
        info_city.text = secondary_profile.postal_code


def generate_xml(apartment_reservation_list: List[ApartmentReservation]):
    root = Element("SBO_AccountsReceivableContainer")

    for item in apartment_reservation_list:
        _append_account_receivable_container_xml(root, item)

    return root
