import dataclasses
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import ClassVar, Dict, List, Optional, Union

from django.utils import translation
from num2words import num2words

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartment
from apartment_application_service.pdf import create_pdf, PDFCurrencyField, PDFData
from apartment_application_service.utils import SafeAttributeObject
from application_form.models import ApartmentReservation
from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
)
from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate
from invoicing.utils import remove_exponent
from users.models import User

HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME = "hitas_contract_template.pdf"
HITAS_COMPLETE_APARTMENT_CONTRACT_PDF_TEMPLATE_FILE_NAME = (
    "hitas_complete_apartment_contract.pdf"  # noqa: E501
)


@dataclasses.dataclass(init=False)
class HitasCompleteApartmentContractPDFData(PDFData):
    def __init__(self, **kwargs):
        names = set([f.name for f in dataclasses.fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    occupant_1: Union[str, None]
    occupant_1_share_of_ownership: Union[str, None]
    occupant_1_address: Union[str, None]
    occupant_1_phone_number: Union[str, None]
    occupant_1_ssn_or_business_id: Union[str, None]
    occupant_1_email: Union[str, None]
    occupant_2: Union[str, None]
    occupant_2_share_of_ownership: Union[str, None]
    occupant_2_address: Union[str, None]
    occupant_2_phone_number: Union[str, None]
    occupant_2_ssn_or_business_id: Union[str, None]
    occupant_2_email: Union[str, None]

    project_housing_company: Union[str, None]
    project_contract_business_id: Union[str, None]
    project_address: Union[str, None]
    project_realty_id: Union[str, None]
    housing_type_ownership: Union[bool, None]
    housing_type_rental: Union[bool, None]
    housing_shares: Union[str, None]
    """Range of numbers as a string, e.g. 1-5"""
    apartment_number: Union[str, None]
    apartment_street_address: Union[str, None]
    floor: Union[str, None]
    apartment_structure: Union[str, None]
    living_area: Union[str, None]
    other_space: Union[str, None]
    other_space_area: Union[str, None]
    project_contract_transfer_restriction_false: Union[bool, None]
    project_contract_transfer_restriction_true: Union[bool, None]
    project_contract_transfer_restriction_text: Union[str, None]
    sales_price: Union[str, None]
    loan_share: Union[str, None]
    loan_share_and_sales_price: Union[str, None]
    buyer_has_paid_down_payment: Union[str, None]
    payment_terms_rest_of_price: Union[str, None]
    payment_bank_1: Union[str, None]
    payment_account_number_1: Union[str, None]
    sales_price_x_0_02: Union[bool, None]
    debt_free_price_x_0_014: Union[bool, None]
    last_payment_dfsp_amount: Union[str, None]

    payment_account_number_2: Union[str, None]
    credit_interest: Union[str, None]
    transfer_of_shares: Union[str, None]
    transfer_of_posession: Union[str, None]
    breach_of_contract_option_1: Union[bool, None]
    breach_of_contract_option_2: Union[bool, None]
    project_contract_collateral_type: Union[str, None]
    guarantee_attachment_exists: Union[bool, None]
    guarantee_attachment_not_exists: Union[bool, None]
    project_contract_construction_permit_requested: Union[str, None]
    project_built_according_to_regulations: Union[str, None]
    other_contract_terms: Union[str, None]
    project_documents_delivered: Union[str, None]
    signing_place_and_time: Union[str, None]
    salesperson_signature: Union[str, None]
    occupants_signatures: Union[str, None]
    sales_price_paid: Union[str, None]
    sales_price_paid_place_and_time: Union[str, None]
    sales_price_paid_salesperson_signature: Union[str, None]
    transfer_of_shares_confirmed: Union[str, None]
    transfer_of_shares_signature: Union[str, None]

    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
        "occupant_1": "P1Ostaja1Nimi",  # "Ostajan nimi Ostaja 1",
        "occupant_1_share_of_ownership": "P1Ostaja1Omistusosuus",  # "Omistusosuus osakkeista Ostaja 1",  # noqa: E501
        "occupant_1_address": "P1Ostaja1Osoite",  # "Osoite Ostaja 1",
        "occupant_1_phone_number": "P1Ostaja1Puhelin",  # "Puhelin Ostaja 1",
        "occupant_1_ssn_or_business_id": "P1Ostaja1Htunnus",  # "Henkilötunnus tai Y-tunnus Ostaja 1",  # noqa: E501
        "occupant_1_email": "P1Ostaja1Sahkoposti",  # "Sähköposti Ostaja 1",
        "occupant_2": "P2Ostaja2Nimi",  # "Ostajan nimi Ostaja 2",
        "occupant_2_share_of_ownership": "P2Ostaja2Omistusosuus",  # "Omistusosuus osakkeista Ostaja 2",  # noqa: E501
        "occupant_2_address": "P2Ostaja2Osoite",  # "Osoite Ostaja 2",
        "occupant_2_phone_number": "P2Ostaja2Puhelin",  # "Puhelin Ostaja 2",
        "occupant_2_ssn_or_business_id": "P2Ostaja2Htunnus",  # "Henkilötunnus tai Y-tunnus Ostaja 2",  # noqa: E501
        "occupant_2_email": "P2Ostaja2Sahkoposti",  # "Sähköposti Ostaja 2",
        "project_housing_company": "P3Yhtionnimi",  # "Yhtiön nimi (jäljempänä yhtiö)",
        "project_contract_business_id": "P3Ytunnus",  # "Y-tunnus",
        "project_address": "P3Yhtionosoite",  # "Yhtiön osoite",
        "project_realty_id": "P3Kiinteistotunnus",  # "Kiinteistötunnus",
        "housing_type_ownership": "P3Omistus",  # "Peruste jolla yhtiö hallitsee kiinteistöä omistus",  # noqa: E501
        "housing_type_rental": "P3Vuokra",  # "Peruste jolla yhtiö hallitsee kiinteistöä vuokra",  # noqa: E501
        "housing_shares": "P3Osakkaidennumerot",  # "Osakkaiden numerot" (xx-yy),
        "apartment_number": "P3Asunnonnro",  # "Asunnon numero",
        "apartment_street_address": "P3Asunnonosoite",  # "Asunnon osoite",
        "floor": "P3Asunnonsijaintikerros",  # "Asunnon sijaintikerros",
        "apartment_structure": "P3Huoneistotyyppi",  # "Huoneistotyyppi (huoneluku)",
        "living_area": "P3Asuintilojenpintaala",  # "Asuintilojen pinta-ala",
        "other_space": "P3Muuttilat",  # "Muut tilat (ei tarkoita yhtiön hallinnassa olevia tiloja)",  # noqa: E501
        "other_space_area": "P3Muidentilojenpintaala",  # "Muiden tilojen pinta-ala",
        "project_contract_transfer_restriction_false": "P3Lunastusoikeuseiole",  # "Ei ole",  # noqa: E501
        "project_contract_transfer_restriction_true": "P3Lunastusoikeuson",  # "On",
        "project_contract_transfer_restriction_text": "P3Lunastusoikeus",  # "Lunastusoikeus ja luovutusta koskevat rajoitteet",  # noqa: E501
        "sales_price": "P4Kauppahinta",  # "Kauppahinta (kirjaimin ja numeroin)",
        "loan_share": "P4Osuuslainoista",  # "Myytyihin osakkeisiin kohdistuva osuus yhtiön lainoista",  # noqa: E501
        "loan_share_and_sales_price": "P4Kauppahintajalainaosuus",  # "Kauppahinta ja yhtiölainaosuus yhteensä (velaton hinta)",  # noqa: E501
        "buyer_has_paid_down_payment": "P4Ostajamaksanutkasirahan",  # "Ostaja on maksanut käsirahan tai varausmaksun, joka luetaan osaksi kauppahintaa",  # noqa: E501
        "payment_terms_rest_of_price": "P4Loppukauppahinnanmaksuehdot",  # "Loppukauppahinnan maksuehdot",  # noqa: E501
        "payment_bank_1": "P4Pankki",  # "Pankki ja konttori",
        "payment_account_number_1": "P4Tilinnumero",  # "Tilin numero",
        "sales_price_x_0_02": "P4002kauppahinta",  # "0,02 kerrottuna kauppahinnalla",
        "debt_free_price_x_0_014": "P40014velatonhinta",  # "0,014 kerrottuna velattomalla hinnalla",  # noqa: E501
        "last_payment_dfsp_amount": "P4Maksettavaviimeinenera",  # "Maksettava viimeinen erä",  # noqa: E501
        "payment_account_number_2": "P4Tilinnumero2",  # "myyjän lukuun tilille nro ...",  # noqa: E501
        "credit_interest": "P5Hyvityskorko",  # "Hyvityskorko",
        "transfer_of_shares": "P5Osakekirjanluovutus",  # "Osakekirjan luovutus",
        "transfer_of_posession": "P5Huoneistonhallinta",  # "Huoneiston hallinta",
        "breach_of_contract_option_1": "P7Vaihtoehto1",  # "Vaihtoehto 1",
        "breach_of_contract_option_2": "P7Vaihtoehto2",  # "Vaihtoehto 2",
        "project_contract_collateral_type": "P8Suorituskyvyttomyysvakuus",  # "Suorituskyvyttömyysvakuus",  # noqa: E501
        "guarantee_attachment_exists": "P8Liiteon",  # "Liite on",
        "guarantee_attachment_not_exists": "P8Liitettaeiole",  # "Liitettä ei ole",
        "project_contract_construction_permit_requested": "P9Haetturakennuslupaa",  # "Yhtiölle on haettu rakennuslupaa",  # noqa: E501
        "project_built_according_to_regulations": "P9Yhtiorakennettumukaisesti",  # "Yhtiö on rakennettu säännösten mukaisesti",  # noqa: E501
        "other_contract_terms": "P10Muutehdot",  # "Muut ehdot ja lisätiedot",
        "project_documents_delivered": "P11Asiakirjat",  # "Asiakirjat",
        "signing_place_and_time": "P12Paikkajaaika",  # "Paikka ja aika",
        "salesperson_signature": "P12Myyjanallekirjoitus",  # "Myyjän allekirjoitus",
        "occupants_signatures": "P12Ostajanallekirjoitus",  # "Ostajan tai ostajien allekirjoitus",  # noqa: E501
        "sales_price_paid": "P12Kauppahintamaksettu",  # "Kauppahinta tai kauppahinnan loppuerä kuitataan maksetuksi",  # noqa: E501
        "sales_price_paid_place_and_time": "P12Kauppahintapaikkajaaika",  # "Paikka ja aika kauppahinta kuitataan maksetuksi aika ja paikka",  # noqa: E501
        "sales_price_paid_salesperson_signature": "P12Kauppahintamyyjanallekirjoitus",  # "Myyjän allekirjoitus kauppahinta kuitataan maksetuksi",  # noqa: E501
        "transfer_of_shares_confirmed": "P12Osakekirjapaikkajaaika",  # "Paikka ja aika osakekirja kuitataan vastaanotetuksi",  # noqa: E501
        "transfer_of_shares_signature": "P12Osakekirjaostajanallekirjoitus",  # "Ostajan tai ostajien allekirjoitus osakekirja kuitataan vastaanotetuksi"  # noqa: E501
    }

    pass


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
    housing_shares: str
    apartment_street_address: Union[str, None]
    apartment_structure: Union[str, None]
    apartment_number: Union[str, None]
    floor: Union[int, None]
    living_area: Union[str, None]
    other_space: Union[str, None]
    other_space_area: Union[str, None]
    project_contract_transfer_restriction_false: Union[bool, None]
    project_contract_transfer_restriction_true: Union[bool, None]
    project_contract_transfer_restriction_text: Union[str, None]
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
    second_last_payment_label: Union[str, None]
    second_last_payment_basis_sales_price: Union[bool, None]
    second_last_payment_basis_debt_free_sales_price: Union[bool, None]
    second_last_payment_dfsp_percentage: Union[Decimal, None]
    second_last_payment_dfsp_amount: Union[PDFCurrencyField, None]
    last_payment_label: Union[str, None]
    last_payment_basis_sales_price: Union[bool, None]
    last_payment_basis_debt_free_sales_price: Union[bool, None]
    last_payment_dfsp_percentage: Union[Decimal, None]
    last_payment_dfsp_amount: Union[PDFCurrencyField, None]
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
        "payment_6_label": "P3Erä6Nro",  # UNUSED
        "payment_7_label": "P3Erä7Nro",  # UNUSED
        "payment_1_amount": "P3Erä1EUR",
        "payment_2_amount": "P3Erä2EUR",
        "payment_3_amount": "P3Erä3EUR",
        "payment_4_amount": "P3Erä4EUR",
        "payment_5_amount": "P3Erä5EUR",
        "payment_6_amount": "P3Erä6EUR",  # UNUSED
        "payment_7_amount": "P3Erä7EUR",  # UNUSED
        "payment_1_due_date": "P3Erä1pvm",
        "payment_2_due_date": "P3Erä2pvm",
        "payment_3_due_date": "P3Erä3pvm",
        "payment_4_due_date": "P3Erä4pvm",
        "payment_5_due_date": "P3Erä5pvm",
        "payment_6_due_date": "P3Erä6pvm",  # UNUSED
        "payment_7_due_date": "P3Erä8pvm",  # UNUSED, NOTE: typo in the template
        "payment_1_percentage": "P3Erä1Pcnt",
        "payment_2_percentage": "P3Erä2Pcnt",
        "payment_3_percentage": "P3Erä3Pcnt",
        "payment_4_percentage": "P3Erä4Pcnt",
        "payment_5_percentage": "P3Erä5Pcnt",
        "payment_6_percentage": "P3Erä6Pcnt",  # UNUSED
        "payment_7_percentage": "P3Erä7Pcnt",  # UNUSED
        "second_last_payment_label": "P3ToiseksiViimeinenErä",
        "second_last_payment_basis_sales_price": "P3TVE008xKh",
        "second_last_payment_sp_percentage": "P3TVEPcntKh",  # UNUSED
        "second_last_payment_sp_amount": "P3TVEEurKh",  # UNUSED
        "second_last_payment_basis_debt_free_sales_price": "P3TVE0056xVh",
        "second_last_payment_dfsp_percentage": "P3TVEPcntVh",
        "second_last_payment_dfsp_amount": "P3TVEEurVh",
        "second_last_payment_comment": "P3TVEEräpäiväIlmoitusKommentti",  # UNUSED
        "last_payment_label": "P3ViimeinenErä",
        "last_payment_basis_sales_price": "P3VE002xKh",
        "last_payment_sp_percentage": "P3VEPcntKh",  # UNUSED
        "last_payment_sp_amount": "P3VEEurKh",  # UNUSED
        "last_payment_basis_debt_free_sales_price": "P3VE0014xVh",
        "last_payment_dfsp_percentage": "P3VEPcntVh",
        "last_payment_dfsp_amount": "P3VEEurVh",
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
        "project_contract_collateral_type": "P17AKL217vakuus",
        "project_contract_default_collateral": "P17AKL219suorituskyvyttymyysvakuus",
        "project_contract_construction_permit_requested": "P19RakennuslupaTietoa",
        "project_contract_other_terms": "P22MuutEhdotOsa1",
        "project_contract_other_terms_2": "P22MuutEhdotOsa2",  # UNUSED
        "project_documents_delivered": "P22LuovutetutAsiakirjat",
        "signing_place_and_time": "AllekirjoitusPaikkaJaAika",
        "salesperson": "AllekirjoitusValtakirjalla",
        "signing_buyers": "AllekirjoitusOstajat",
        "collateral_place_and_time": "AKL17VakuuksienAsetusPaikkaJaAika",  # UNUSED
        "project_contract_collateral_bank_and_address": "TurvaAsiakirjojenSäilyttäjä",
    }


def create_hitas_contract_pdf(
    reservation: ApartmentReservation,
    sales_price_paid_place: str,
    sales_price_paid_time: str,
    salesperson: User,
) -> BytesIO:
    customer = SafeAttributeObject(reservation.customer)
    primary_profile = SafeAttributeObject(customer.primary_profile)
    secondary_profile = SafeAttributeObject(customer.secondary_profile)
    apartment: ApartmentDocument = SafeAttributeObject(
        get_apartment(reservation.apartment_uuid, include_project_fields=True)
    )

    # use contract for complete apartment
    # can possibly be None, use bool() to convert to False in that case
    complete_apartment = bool(apartment.project_use_complete_contract)

    (
        payment_1,
        payment_2,
        payment_3,
        payment_4,
        payment_5,
        payment_6,
        payment_7,
    ) = _get_numbered_installments(apartment, reservation)

    down_payment = SafeAttributeObject(
        reservation.apartment_installments.filter(
            type=InstallmentType.DOWN_PAYMENT
        ).first()
    )

    sales_price_paid_place_and_time = (
        f"{sales_price_paid_place} {sales_price_paid_time}"
    )

    def hitas_price(cents: Union[int, None]) -> Union[PDFCurrencyField, None]:
        """Turns the price in cents to whole euros (division by 100). Outputs
        a PDFCurrencyField prefilled with a string that has the euro sum
        as words (in Finnish) and as numbers.

        e.g.
        12000 -> "tuhat kaksisataa 1200 €"

        11000000 -> "satakymmenentuhatta 110000 €"

        31115224 -> "kolmekymmentäyksimiljoonaa sataviisitoistatuhatta
        kaksisataakaksikymmentäneljä 31115224 €"

        Args:
            cents (Union[int, None]): The sum in cents

        Returns: Union[PDFCurrencyField, None]:
        """
        if cents is None:
            return None
        return PDFCurrencyField(
            prefix=num2words(Decimal(cents) / 100, lang="fi") + " ",
            cents=cents,
            suffix=" €",
        )

    contract_data = {
        "occupant_1": primary_profile.full_name,
        "occupant_1_share_of_ownership": None,
        "occupant_1_address": (
            (primary_profile.street_address or "")
            + ", "
            + (primary_profile.postal_code or "")
            + " "
            + (primary_profile.city or "")
        ).strip(),
        "occupant_1_phone_number": primary_profile.phone_number,
        "occupant_1_email": primary_profile.email,
        "occupant_1_ssn_or_business_id": primary_profile.national_identification_number,
        "occupant_2": secondary_profile.full_name,
        "occupant_2_share_of_ownership": None,
        "occupant_2_address": (
            (secondary_profile.street_address or "")
            + ", "
            + (secondary_profile.postal_code or "")
            + " "
            + (secondary_profile.city or "")
        ).strip(),
        "occupant_2_phone_number": secondary_profile.phone_number,
        "occupant_2_email": secondary_profile.email,
        "occupant_2_ssn_or_business_id": secondary_profile.national_identification_number,  # noqa: E501
        "project_housing_company": apartment.project_housing_company,
        "project_contract_business_id": apartment.project_contract_business_id,
        "project_address": "  ".join(
            [
                apartment.project_street_address,
                f"{apartment.project_postal_code} {apartment.project_city}",
            ]
        ),
        "project_realty_id": apartment.project_realty_id,
        "housing_type_ownership": False,
        "housing_type_rental": True,
        "housing_shares": f"{apartment.stock_start_number or ''} - {apartment.stock_end_number or ''}",  # noqa: E501
        "apartment_street_address": None,
        "apartment_structure": apartment.apartment_structure,
        "apartment_number": apartment.apartment_number,
        "floor": apartment.floor,
        "living_area": apartment.living_area,
        "other_space": None,
        "other_space_area": None,
        "project_contract_transfer_restriction_false": apartment.project_contract_transfer_restriction  # noqa E501
        is False,
        "project_contract_transfer_restriction_true": apartment.project_contract_transfer_restriction,  # noqa E501
        "project_contract_transfer_restriction_text": apartment.project_contract_article_of_association,  # noqa E501
        "project_contract_material_selection_later_false": apartment.project_contract_material_selection_later  # noqa E501
        is False,
        "project_contract_material_selection_later_true": apartment.project_contract_material_selection_later,  # noqa E501
        "project_contract_material_selection_description": apartment.project_contract_material_selection_description,  # noqa E501
        "project_contract_material_selection_date": apartment.project_contract_material_selection_date,  # noqa E501
        "sales_price": hitas_price(apartment.sales_price),
        "loan_share": hitas_price(apartment.loan_share),
        "debt_free_sales_price": hitas_price(apartment.debt_free_sales_price),
        "payment_1_label": payment_1.type,
        "payment_1_amount": PDFCurrencyField(euros=payment_1.value),
        "payment_1_due_date": payment_1.due_date,
        "payment_1_percentage": payment_1._percentage,
        "payment_2_label": payment_2.type,
        "payment_2_amount": PDFCurrencyField(euros=payment_2.value),
        "payment_2_due_date": payment_2.due_date,
        "payment_2_percentage": payment_2._percentage,
        "payment_3_label": payment_3.type,
        "payment_3_amount": PDFCurrencyField(euros=payment_3.value),
        "payment_3_due_date": payment_3.due_date,
        "payment_3_percentage": payment_3._percentage,
        "payment_4_label": payment_4.type,
        "payment_4_amount": PDFCurrencyField(euros=payment_4.value),
        "payment_4_due_date": payment_4.due_date,
        "payment_4_percentage": payment_4._percentage,
        "payment_5_label": payment_5.type,
        "payment_5_amount": PDFCurrencyField(euros=payment_5.value),
        "payment_5_due_date": payment_5.due_date,
        "payment_5_percentage": payment_5._percentage,
        "second_last_payment_label": "6",
        "second_last_payment_basis_sales_price": False,
        "second_last_payment_basis_debt_free_sales_price": True,
        "second_last_payment_dfsp_percentage": payment_6._percentage,
        "second_last_payment_dfsp_amount": PDFCurrencyField(euros=payment_6.value),
        "last_payment_label": "7",
        "last_payment_basis_sales_price": False,
        "last_payment_basis_debt_free_sales_price": True,
        "last_payment_dfsp_percentage": payment_7._percentage,
        "last_payment_dfsp_amount": PDFCurrencyField(euros=payment_7.value),
        "payment_bank_1": apartment.project_contract_depositary,
        "payment_account_number_1": apartment.project_regular_bank_account,
        "payment_bank_2": apartment.project_contract_depositary,
        "payment_account_number_2": apartment.project_barred_bank_account,
        "down_payment_amount": PDFCurrencyField(
            euros=down_payment.amount if down_payment.amount else Decimal(0),
            suffix=" €",
        ),
        "project_contract_apartment_completion_selection_1": apartment.project_contract_apartment_completion_selection_1,  # noqa E501
        "project_contract_apartment_completion_selection_1_date": apartment.project_contract_apartment_completion_selection_1_date,  # noqa E501
        "project_contract_apartment_completion_selection_2": apartment.project_contract_apartment_completion_selection_2,  # noqa E501
        "project_contract_apartment_completion_selection_2_start": apartment.project_contract_apartment_completion_selection_2_start,  # noqa E501
        "project_contract_apartment_completion_selection_2_end": apartment.project_contract_apartment_completion_selection_2_end,  # noqa E501
        "project_contract_apartment_completion_selection_3": apartment.project_contract_apartment_completion_selection_3,  # noqa E501
        "project_contract_apartment_completion_selection_3_date": apartment.project_contract_apartment_completion_selection_3_date,  # noqa E501
        "project_contract_depositary": apartment.project_contract_depositary,
        "project_contract_repository": apartment.project_contract_repository,
        "breach_of_contract_option_1": False,
        "breach_of_contract_option_2": True,
        "project_contract_collateral_type": apartment.project_contract_collateral_type,
        "project_contract_default_collateral": apartment.project_contract_default_collateral,  # noqa E501
        "project_contract_construction_permit_requested": (
            (apartment.project_contract_construction_permit_requested)
            if apartment.project_contract_construction_permit_requested
            else None
        ),
        "project_contract_other_terms": apartment.project_contract_combined_terms,
        "project_documents_delivered": apartment.project_documents_delivered,
        "signing_place_and_time": sales_price_paid_place_and_time,
        "salesperson": salesperson.profile_or_user_full_name,
        "signing_buyers": " & ".join(
            name
            for name in [primary_profile.full_name, secondary_profile.full_name]
            if name
        ),
        "project_contract_collateral_bank_and_address": "  ".join(
            [
                apartment.project_contract_depositary or "",
                apartment.project_contract_repository or "",
            ]
        ),
    }

    # override language to Finnish, as the user's browser settings etc.
    # shouldn't affect the printed out PDFs
    # further info on how Django resolves language preference:
    # https://docs.djangoproject.com/en/5.1/topics/i18n/translation/
    with translation.override("fi"):
        payment_1_price = hitas_price(payment_1.value * 100)
        payment_terms_rest_of_price = f"{payment_1.type.label}"
        if payment_1.due_date:
            due_date = payment_1.due_date.strftime("%d.%m.%Y")
            payment_terms_rest_of_price += f" {due_date}"

        payment_terms_rest_of_price += f" {payment_1_price.formatted_number_string()} {payment_1_price.suffix}"  # noqa: E501

    # full apartment contract data is mostly the same fields but with some changes
    full_apartment_contract_data = {
        **contract_data,
        "building_permit_applied_for": apartment.project_construction_permit_claim,
        "buyer_has_paid_down_payment": "",
        "credit_interest": "0,00%",
        "debt_free_price_x_0_014": True,
        "project_documents_delivered": apartment.project_documents_delivered,
        "final_payment": "final_payment",
        "guarantee": "guarantee",
        "guarantee_attachment_exists": True,
        "guarantee_attachment_not_exists": False,
        "project_contract_collateral_type": apartment.project_contract_default_collateral,  # noqa: E501
        "loan_share_and_sales_price": hitas_price(apartment.debt_free_sales_price),
        "occupants_signatures": contract_data["signing_buyers"],
        "other_contract_terms": apartment.project_contract_combined_terms,
        "payment_terms_rest_of_price": payment_terms_rest_of_price,
        "project_built_according_to_regulations": "",  # noqa: E501
        "sales_price_paid": "",
        "sales_price_paid_place_and_time": sales_price_paid_place_and_time,  # noqa: E501
        "sales_price_paid_salesperson_signature": salesperson.profile_or_user_full_name,
        "sales_price_x_0_02": False,
        "other_space": "",
        "other_space_area": "",
        "salesperson_signature": "",
        "transfer_of_posession": apartment.project_possession_transfer_date,
        "transfer_of_shares": apartment.project_transfer_of_shares_date,
        "transfer_of_shares_confirmed": "",
        "transfer_of_shares_signature": "",
    }

    contract_dataclass = HitasContractPDFData
    pdf_template_path = HITAS_CONTRACT_PDF_TEMPLATE_FILE_NAME

    if complete_apartment:
        contract_dataclass = HitasCompleteApartmentContractPDFData
        contract_data = full_apartment_contract_data
        pdf_template_path = HITAS_COMPLETE_APARTMENT_CONTRACT_PDF_TEMPLATE_FILE_NAME

    pdf_data = contract_dataclass(**contract_data)
    return create_hitas_contract_pdf_from_data(pdf_data, pdf_template_path)


def create_hitas_complete_apartment_contract_pdf_from_data(
    pdf_data: HitasCompleteApartmentContractPDFData,
) -> BytesIO:
    return create_pdf(
        HITAS_COMPLETE_APARTMENT_CONTRACT_PDF_TEMPLATE_FILE_NAME, pdf_data
    )


def create_hitas_contract_pdf_from_data(
    pdf_data: Union[HitasContractPDFData, HitasCompleteApartmentContractPDFData],
    template_path: str,
) -> BytesIO:
    return create_pdf(template_path, pdf_data)


def _get_numbered_installments(
    apartment, reservation: ApartmentReservation
) -> List[ApartmentInstallment]:
    try:
        flexible_type = ProjectInstallmentTemplate.objects.get(
            project_uuid=apartment.project_uuid,
            unit=InstallmentUnit.PERCENT,
            percentage_specifier=InstallmentPercentageSpecifier.SALES_PRICE_FLEXIBLE,
        ).type
    except ProjectInstallmentTemplate.DoesNotExist:
        flexible_type = None

    numbered_installments = []
    flexible_installment = None
    cumulative_percentage = 0

    for payment_type in (
        InstallmentType.PAYMENT_1,
        InstallmentType.PAYMENT_2,
        InstallmentType.PAYMENT_3,
        InstallmentType.PAYMENT_4,
        InstallmentType.PAYMENT_5,
        InstallmentType.PAYMENT_6,
        InstallmentType.PAYMENT_7,
    ):
        if installment := reservation.apartment_installments.filter(
            type=payment_type
        ).first():
            if installment.type == flexible_type:
                flexible_installment = installment
            else:
                percentage = _get_percentage(installment, apartment.sales_price)
                # ApartmentInstallment model doesn't actually have a percentage field,
                # we add it here dynamically to the instance to make life easier
                installment._percentage = percentage
                cumulative_percentage += percentage
        numbered_installments.append(SafeAttributeObject(installment))

    if flexible_installment:
        flexible_installment._percentage = Decimal(100) - cumulative_percentage

    return numbered_installments


def _get_percentage(
    apartment_installment: ApartmentInstallment,
    sales_price_in_cents: int,
) -> Optional[Decimal]:
    if not apartment_installment.value:
        return None
    # round to one decimal place and remove trailing zeros
    return remove_exponent(
        (
            apartment_installment.value / (Decimal(sales_price_in_cents) / 100) * 100
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )
