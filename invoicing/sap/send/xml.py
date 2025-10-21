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
from typing import List, Union
from xml.etree.ElementTree import Element, SubElement, tostring

from django.conf import settings
from django.db.models import QuerySet

from invoicing.models import ApartmentInstallment
from invoicing.sap.send.xml_utils import (
    get_base_line_date_string,
    get_installment_type_text,
    get_posting_date,
    get_wbs_element,
)


def generate_installments_xml(
    apartment_installments: Union[
        List[ApartmentInstallment], QuerySet[ApartmentInstallment]
    ],
) -> bytes:
    xml_content = generate_installments_xml_element(apartment_installments)
    return tostring(xml_content, encoding="utf-8", xml_declaration=True)


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
    posting_date.text = get_posting_date(apartment_installment.due_date)

    # FI: Viite
    reference = SubElement(sbo_account_receivable, "Reference")
    reference.text = str(apartment_installment.invoice_number)

    # FI: Tositteen otsikkoteksti
    header_text = SubElement(sbo_account_receivable, "HeaderText")
    header_text.text = get_installment_type_text(apartment_installment.type)

    # FI: Valuutta-avain
    currency_code = SubElement(sbo_account_receivable, "CurrencyCode")
    currency_code.text = settings.SAP["CURRENCY_CODE"]

    # Debit line information
    debit_line_item = SubElement(sbo_account_receivable, "LineItem")

    # FI: Summa tositevaluuttana
    debit_amount_in_document_currency = SubElement(
        debit_line_item, "AmountInDocumentCurrency"
    )
    debit_amount_in_document_currency.text = str(apartment_installment.value).replace(
        ".", ","
    )

    # FI: Riviteksti
    debit_line_text = SubElement(debit_line_item, "LineText")
    debit_line_text.text = header_text.text

    primary_profile = (
        apartment_installment.apartment_reservation.customer.primary_profile
    )  # NOQA: E501

    # FI: Henkilöasiakkaan HeTu
    customer_id = SubElement(debit_line_item, "CustomerID")
    customer_id.text = primary_profile.national_identification_number

    # FI: Eräpäivän lakennan peruspäivämäärä
    base_line_date = SubElement(debit_line_item, "BaseLineDate")
    base_line_date.text = get_base_line_date_string(apartment_installment.due_date)

    # FI: Maksuehtoavain
    payment_terms = SubElement(debit_line_item, "PaymentTerms")
    payment_terms.text = settings.SAP.get("PAYMENT_TERMS")

    # FI: Maksuviite
    reference_id = SubElement(debit_line_item, "ReferenceId")
    reference_id.text = apartment_installment.reference_number

    # FI: Infotieto Henkilöasiakkaan HeTu
    info_customer_id = SubElement(debit_line_item, "InfoCustomerID")
    info_customer_id.text = customer_id.text

    # FI: Infotieto nimi rivi 1
    info_name_1 = SubElement(debit_line_item, "InfoName1")
    info_name_1.text = primary_profile.last_name

    # FI: Infotieto nimi rivi 2
    info_name_2 = SubElement(debit_line_item, "InfoName2")
    info_name_2.text = primary_profile.first_name

    if (
        secondary_profile := apartment_installment.apartment_reservation.customer.secondary_profile  # NOQA: E501
    ):
        # FI: Infotieto nimi rivi 3
        info_name_3 = SubElement(debit_line_item, "InfoName3")
        info_name_3.text = secondary_profile.last_name

        # FI: Infotieto nimi rivi 4
        info_name_4 = SubElement(debit_line_item, "InfoName4")
        info_name_4.text = secondary_profile.first_name

    # FI: Infotieto osoite rivi 1
    info_address_1 = SubElement(debit_line_item, "InfoAddress1")
    info_address_1.text = primary_profile.street_address

    # FI: Infotieto paikkakunta
    info_city = SubElement(debit_line_item, "InfoCity")
    info_city.text = primary_profile.city

    # FI: Infotieto postinumero
    info_postal_code = SubElement(debit_line_item, "InfoPostalcode")
    info_postal_code.text = primary_profile.postal_code

    # Credit line information
    credit_line_item = SubElement(sbo_account_receivable, "LineItem")

    # FI: Arvonlisäverotunnus
    tax_code = SubElement(credit_line_item, "TaxCode")
    tax_code.text = settings.SAP["TAX_CODE"]

    # FI: Summa tositevaluuttana
    credit_amount_in_document_currency = SubElement(
        credit_line_item, "AmountInDocumentCurrency"
    )
    credit_amount_in_document_currency.text = str(
        -1 * apartment_installment.value
    ).replace(".", ",")

    # FI: Riviteksti
    credit_line_text = SubElement(credit_line_item, "LineText")
    credit_line_text.text = header_text.text

    # FI: Pääkirjanpidon pääkirjatili
    gl_account = SubElement(credit_line_item, "GLAccount")
    gl_account.text = settings.SAP["GL_ACCOUNT"]

    # FI: Projektirakenteen osa (PRR-osa)
    wbs_element = SubElement(credit_line_item, "WBS_Element")
    wbs_element.text = get_wbs_element(apartment_installment)

    return sbo_account_receivable


def generate_installments_xml_element(
    apartment_installments: List[ApartmentInstallment],
):
    root = Element("SBO_AccountsReceivableContainer")

    for item in apartment_installments:
        _append_account_receivable_container_xml(root, item)

    return root
