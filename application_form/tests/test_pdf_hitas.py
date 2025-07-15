import datetime
import pathlib
import unittest
from decimal import Decimal

from apartment_application_service.pdf import PDFCurrencyField as CF

from ..pdf.hitas import (
    HitasCompleteApartmentContractPDFData,
    create_hitas_complete_apartment_contract_pdf_from_data,
    create_hitas_contract_pdf_from_data,
    HitasContractPDFData,
)
from .pdf_utils import get_cleaned_pdf_texts, remove_pdf_id

# This variable should be normally False, but can be set temporarily to
# True to override the expected test result PDF file.  This is useful
# when either the template has changed or the test data has changed and
# a new expected result PDF file needs to be generated.  Remember to
# revert this variable back to False to ensure that the test is
# actually testing the expected result.
OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE = False

my_dir = pathlib.Path(__file__).parent


CONTRACT_PDF_DATA = HitasContractPDFData(
    # 1
    occupant_1="Matti Meikäläinen",
    occupant_1_share_of_ownership="49%",
    occupant_1_address="Pöhkökatu 1 C 51",
    occupant_1_phone_number="040 123 4567",
    occupant_1_email="matti.meikalainen@meikä.fi",
    occupant_1_ssn_or_business_id="010101-1234",
    occupant_2="Maija Meikäläinen",
    occupant_2_share_of_ownership="51%",
    occupant_2_address="Möhkälekatu 2 F 64",
    occupant_2_phone_number="050 987 6543",
    occupant_2_email="maija.meikalainen@meikä.fi",
    occupant_2_ssn_or_business_id="020202-2345",
    #
    # 2
    project_housing_company="Asumiskolo Pöhkö",
    project_contract_business_id="0912770-2",
    project_address="Mörkötie 12",
    project_realty_id="123-456-789-0",
    housing_type_ownership=False,
    housing_type_rental=True,
    housing_shares="123–456",
    apartment_street_address="Mörkötie 12 C 51",
    apartment_structure="4h+k+s+yöpymisparvi",
    apartment_number="C 51",
    floor=5,
    living_area="125.3",
    other_space=None,
    other_space_area=None,
    project_contract_transfer_restriction_false=False,
    project_contract_transfer_restriction_true=True,
    project_contract_transfer_restriction_text="ks. yhtiöjärjestyksen 9-13.",
    project_contract_material_selection_later_false=True,
    project_contract_material_selection_later_true=False,
    project_contract_material_selection_description="myöhemmin",
    project_contract_material_selection_date=datetime.date(2022, 12, 19),
    #
    # 3
    sales_price=CF(euros=Decimal("1234.56")),
    loan_share=CF(euros=Decimal("2345.67")),
    debt_free_sales_price=CF(euros=Decimal("3456.78")),
    payment_1_label="Maksuerä 1",
    payment_1_amount=CF(euros=Decimal("4567.89")),
    payment_1_due_date=datetime.date(2020, 8, 19),
    payment_1_percentage=Decimal("12.5"),
    payment_2_label="Maksuerä 2",
    payment_2_amount=CF(euros=Decimal("5678.90")),
    payment_2_due_date=datetime.date(2020, 9, 3),
    payment_2_percentage=Decimal("25.0"),
    payment_3_label="Maksuerä 3",
    payment_3_amount=CF(euros=Decimal("6789.01")),
    payment_3_due_date=datetime.date(2020, 10, 3),
    payment_3_percentage=Decimal("37.5"),
    payment_4_label="Maksuerä 4",
    payment_4_amount=CF(euros=Decimal("7890.12")),
    payment_4_due_date=datetime.date(2020, 11, 3),
    payment_4_percentage=Decimal("50.0"),
    payment_5_label="Maksuerä 5",
    payment_5_amount=CF(euros=Decimal("8901.23")),
    payment_5_due_date=datetime.date(2020, 12, 3),
    payment_5_percentage=Decimal("62.5"),
    second_last_payment_label="6",
    second_last_payment_basis_sales_price=True,
    second_last_payment_basis_debt_free_sales_price=True,
    second_last_payment_dfsp_percentage=Decimal("72.5"),
    second_last_payment_dfsp_amount=CF(euros=Decimal("9012.34")),
    last_payment_label="7",
    last_payment_basis_sales_price=True,
    last_payment_basis_debt_free_sales_price=True,
    last_payment_dfsp_percentage=Decimal("82.5"),
    last_payment_dfsp_amount=CF(euros=Decimal("10123.45")),
    payment_bank_1="Nordea",
    payment_account_number_1="FI12 3456 7890 1234 56",
    payment_bank_2="Nordea",
    payment_account_number_2="FI34 5678 9012 3456 78",
    down_payment_amount=CF(euros=Decimal("1234.56")),
    #
    # 5
    project_contract_apartment_completion_selection_1=True,
    project_contract_apartment_completion_selection_1_date=datetime.date(2021, 3, 31),
    project_contract_apartment_completion_selection_2=False,
    project_contract_apartment_completion_selection_2_start=datetime.date(2021, 4, 1),
    project_contract_apartment_completion_selection_2_end=datetime.date(2021, 5, 31),
    project_contract_apartment_completion_selection_3=True,
    project_contract_apartment_completion_selection_3_date=datetime.date(2021, 6, 30),
    #
    # 9
    project_contract_depositary="Ö-Pankki Oyj",
    project_contract_repository="PL 123, 00020 Ö-Pankki",
    #
    # 15
    breach_of_contract_option_1=True,
    breach_of_contract_option_2=False,
    #
    # 17
    project_contract_collateral_type="kiinteistökiinnitys",
    project_contract_default_collateral="pankkitalletus 100 € Ä-Pankki Oyj:ssä",
    #
    # 19
    project_contract_construction_permit_requested=datetime.date(2020, 7, 1),
    #
    # 22
    project_contract_other_terms="Muita ehtoja ja myös sellasta",
    project_documents_delivered="ehkä",
    #
    # contract part "allekirjoitukset" (signings)
    signing_place_and_time="Mörkökylässä 1.7.2020",
    signing_buyers="Matti Meikäläinen & Maija Meikäläinen",
    salesperson="Mörkö",
    project_contract_collateral_bank_and_address="Ö-Pankki Oyj, PL 123, 00020 Ö-Pankki",
)

COMPLETE_CONTRACT_PDF_DATA = HitasCompleteApartmentContractPDFData(
    occupant_1="Matti Meikäläinen",
    occupant_1_share_of_ownership="49%",
    occupant_1_address="Pöhkökatu 1 C 51",
    occupant_1_phone_number="040 123 4567",
    occupant_1_ssn_or_business_id="010101-1234",
    occupant_1_email="matti.meikalainen@meikä.fi",
    occupant_2="Maija Meikäläinen",
    occupant_2_share_of_ownership="51%",
    occupant_2_address="Möhkälekatu 2 F 64",
    occupant_2_phone_number="050 987 6543",
    occupant_2_ssn_or_business_id="020202-2345",
    occupant_2_email="maija.meikalainen@meikä.fi",
    project_housing_company="Asumiskolo Pöhkö",
    project_contract_business_id="0912770-2",
    project_address="Mörkötie 12",
    project_realty_id="123-456-789-0",
    housing_type_ownership=False,
    housing_type_rental=True,
    housing_shares="123-456",
    apartment_number="C 51",
    apartment_street_address="Mörkötie 12 C 51",
    floor=5,
    apartment_structure="4h+k+s+yöpymisparvi",
    living_area="125.3",
    other_space="Muu tila",
    other_space_area="10.5",
    project_contract_transfer_restriction_false=False,
    project_contract_transfer_restriction_true=True,
    project_contract_transfer_restriction="Lunastusoikeus lisätiedot",
    sales_price=CF(euros=Decimal("1234.56")),
    loan_share=CF(euros=Decimal("2345.67")),
    loan_share_and_sales_price=CF(euros=Decimal("3580.23")),
    buyer_has_paid_down_payment="1.1.2024",
    payment_terms_rest_of_price="Loppukauppahinnan maksuehdot ovat seuraavanlaiset...",
    payment_bank_1="Testi pankki",
    payment_account_number_1="FI21 1234 5600 0007 85",
    sales_price_x_0_02=False,
    debt_free_price_x_0_014=True,
    last_payment_dfsp_amount=CF(euros=Decimal("1234.56")),
    final_payment=CF(euros=Decimal("17.30")),
    payment_account_number_2="FI21 1234 5600 0007 87",
    credit_interest="12",
    transfer_of_shares="Testi osakkeiden luovutus",
    transfer_of_posession="Testi hallinta luovutus",
    breach_of_contract_option_1=True,
    breach_of_contract_option_2=False,
    project_contract_collateral_type="Kiinteistökiinnitys",
    inability_to_pay_guarantee="Suorituskyvyttömyysvakuus",
    guarantee="Muu vakuus",
    guarantee_attachment_exists=True,
    guarantee_attachment_not_exists=False,
    building_permit_applied_for="Haettu 10.11.2023",
    project_built_according_to_regulations="Rakennettu säännösten mukaan",
    other_contract_terms="Muut sopimusehdot",
    documents="Ostava on perehtynyt seuraaviin asiakirjoihin",
    signing_place_and_time="22.1.2024 Helsinki",
    salesperson_signature="Markku Myyjä",
    occupants_signatures="Matti Meikäläinen",
    sales_price_paid="Kuitattu maksetuksi",
    sales_price_paid_place_and_time="Helsingissä 22.1.2024",
    sales_price_paid_salesperson_signature="Matti Myyjä",
    transfer_of_shares_confirmed="22.1.2024",
    transfer_of_shares_signature="Matti Myyjä",
)


class TesthitasCompleteApartmentContractPdfFromData(unittest.TestCase):
    def setUp(self) -> None:
        pdf = create_hitas_complete_apartment_contract_pdf_from_data(
            COMPLETE_CONTRACT_PDF_DATA
        )
        self.pdf_content = pdf.getvalue()

        if OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE:
            write_file(
                "hitas_complete_apartment_contract_test_result.pdf", self.pdf_content
            )
            assert False, "Not testing, because PDF file was overridden."

        self.expected_pdf_content = read_file(
            "hitas_complete_apartment_contract_test_result.pdf"
        )

        return super().setUp()

    def test_pdf_content_is_not_empty(self):
        assert self.pdf_content


class TesthitasContractPdfFromData(unittest.TestCase):
    def setUp(self) -> None:
        pdf = create_hitas_contract_pdf_from_data(CONTRACT_PDF_DATA)
        self.pdf_content = pdf.getvalue()

        if OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE:
            write_file("hitas_contract_test_result.pdf", self.pdf_content)
            assert False, "Not testing, because PDF file was overridden."

        self.expected_pdf_content = read_file("hitas_contract_test_result.pdf")

        return super().setUp()

    def test_pdf_content_is_not_empty(self):
        assert self.pdf_content

    def test_pdf_content_text_is_correct(self):
        assert get_cleaned_pdf_texts(self.pdf_content) == [
            "Helsinki",
            "Asuinhuoneiston rakentamisvaiheen kauppakirja",
            "1 Sopijapuolet",
            "Myyjän nimi",
            "Helsingin kaupunki / Kaupunkiympäristö, asuntotuotanto",
            "Osoite",
            "PL 58226 / Työpajankatu 8, 00099 Helsingin kaupunki",
            "Puhelin Henkilötunnus tai Y-tunnus",
            "0201256-6",
            "Ostajan nimi Ostajan nimi",
            "Matti Meikäläinen Maija Meikäläinen",
            "Omistusosuus osakkeista 1 Omistusosuus osakkeista 1",
            "49% 51%",
            "Osoite Osoite",
            "Pöhkökatu 1 C 51 Möhkälekatu 2 F 64",
            "Puhelin Puhelin",
            "040 123 4567 050 987 6543",
            "Sähköposti Sähköposti",
            "matti.meikalainen@meikä.fi maija.meikalainen@meikä.fi",
            "Henkilötunnus tai Y-tunnus Henkilötunnus tai Y-tunnus",
            "010101-1234 020202-2345",
            "1 Ellei omistusosuutta merkitä, ostajien omistusosuudet oletetaan yhtä "
            "suuriksi",
            "1",
            "2 Kaupan kohde",
            "Yhtiön toiminimi (jäljempänä yhtiö) Y-tunnus",
            "Asumiskolo Pöhkö 0912770-2",
            "Yhtiön osoite",
            "Mörkötie 12",
            "Kiinteistötunnus Peruste, jolla yhtiö hallitsee kiinteistöä",
            "123-456-789-0 □ omistus",
            "■ vuokra",
            "□",
            "Osakkeiden numerot Osakkeet oikeuttavat asunnon",
            "123–456 nro C 51 hallintaan yhtiön",
            "omistamassa rakennuksessa",
            "Asunnon osoite (jos eri kuin yhtiön osoite)",
            "Mörkötie 12 C 51",
            "Asunnon sijaintikerros Huoneistotyyppi (huoneluku) Asuintilojen pinta-ala m2",
            "5 4h+k+s+yöpymisparvi 125.3",
            "Muut tilat 2 Muiden tilojen pinta-ala m2",
            "Asunnon käyttöä tai osakkeiden luovutusoikeutta koskevat rajoitukset sekä "
            "yhtiöllä,",
            "osakkeenomistajalla tai kunnalla oleva lunastusoikeus",
            "□ ei ole",
            "■ on",
            "□",
            "ks. yhtiöjärjestyksen 9-13.",
            "Ostaja täsmentää valintansa kauppahintaan sisältyvistä asunnon materiaali- "
            "tai",
            "varustevaihtoehdoista myöhemmin (rasti ruutuun)",
            "■ ei",
            "□",
            "□ kyllä",
            "Miltä osin",
            "myöhemmin",
            "Täsmennyksen ajankohta",
            "19.12.2022",
            "Jos ostaja ei tee täsmennystä sovittuna ajankohtana, myyjä täsmentää nämä "
            "ominaisuudet",
            "2 Ei tarkoita yhtiön hallinnassa olevia tiloja",
            "2",
            "3 Kauppahinta ja sen maksaminen",
            "Kauppahinta (kirjaimin ja numeroin)",
            "1 234,56",
            "Myytyihin osakkeisiin kohdistuva osuus yhtiön lainoista",
            "(Ks. Yhtiöjärjestyksen määräykset lainaosuuden pois maksamisesta)",
            "2 345,67",
            "Kauppahinta ja yhtiölainaosuus yhteensä (velaton hinta)",
            "(Ks kohta 11. Taloussuunnitelman muuttaminen)",
            "3 456,78",
            "Kauppahinta määräytyy maksettavaksi seuraavan aikataulun mukaisesti 3",
            "Eränumero Eräpäivämäärä % €",
            "Maksuerä 1 19.8.2020 12,5 4 567,89",
            "Maksuerä 2 3.9.2020 25,0 5 678,90",
            "Maksuerä 3 3.10.2020 37,5 6 789,01",
            "Maksuerä 4 3.11.2020 50,0 7 890,12",
            "Maksuerä 5 3.12.2020 62,5 8 901,23",
            "Toiseksi viim. erä 4 % €",
            "6",
            "(valittava suurempi)",
            "■ 0,08 x kauppahinta",
            "□",
            "■ 0,056 x velaton hinta",
            "□ 72,5 9 012,34",
            "Eräpäivä ilmoitetaan muuttokirjeessä",
            "3",
            "Viimeinen erä 4 % €",
            "7",
            "(valittava suurempi)",
            "■ 0,02 x kauppahinta",
            "□",
            "■ 0,014 x velaton hinta",
            "□ 82,5 10 123,45",
            "Eräpäivä ilmoitetaan muuttokirjeessä",
            "Kauppahinnasta erät nro (merkitään toiseksi viimeinen erä)",
            "on maksettava myyjän rakennushanketta varten avaamalle pankkitilille",
            "Pankki Tilinumero",
            "Nordea FI12 3456 7890 1234 56",
            "Viimeinen kauppahintaerä on maksettava tallettamalla se myyjän tilille",
            "Pankki Tilinumero",
            "Nordea FI34 5678 9012 3456 78",
            "Ostajan maksama käsiraha/varausmaksu",
            "1 234,56",
            "sisältyy 1. kauppahintaerään ja ostaja saa vähentää sen 1. kauppahintaerän "
            "maksun",
            "yhteydessä",
            "Maksuerien tulee vastata myyjän suorituksen arvoa siten, ettei selvää tai "
            "jatkuvaa",
            "suoritusten epätasapainoa ostajan vahingoksi pääse syntymään. Toiseksi "
            "viimeinen ja",
            "viimeinen erä saavat kuitenkin erääntyä vasta, kun ostajalla on ollut "
            "kohtuullinen tilaisuus",
            "tarkastaa asunto ja asunnon hallinta on ollut luovutettavissa ostajalle.",
            "Jos ostaja aikoo maksaa viimeisen kauppahintaerän ennen sen erääntymistä, "
            "tulee hänen",
            "kirjallisesti tiedustella myyjältä, ottaako myyjä suorituksen vastaan. "
            "Myyjällä on oikeus",
            "kieltäytyä vastaanottamasta viimeistä erää ennen sen erääntymisajankohtaa.",
            "Myyjä saa nostaa viimeisen kauppahintaerän ja sille mahdollisen kertyneen "
            "talletuskoron",
            "pankista aikaisintaan kuukauden kuluttua siitä, kun asunnon hallinta on "
            "luovutettu ostajalle,",
            "jollei ostaja asuntokauppalain 4 luvun 29 §:n mukaan ole oikeutettu "
            "kieltämään viimeisen",
            "erän vapauttamista ja kirjallisesti tällä perusteella tätä ennen kiellä "
            "pankkia luovuttamasta",
            "4",
            "talletusta tai osaa siitä myyjälle. Ostajan on ilmoitettava kiellosta ja sen "
            "perusteista myös",
            "myyjälle.",
            "3 Jos kauppakirjaan merkitään vain rakennusvaihe, myyjän on ilmoitettava "
            "ostajalle",
            "kirjallisesti kunkin rakennusvaiheen valmistumista. Kauppahintaerä erääntyy "
            "tällöin",
            "maksettavaksi 14 päivän kuluttua ilmoituksen postin kuljetettavaksi "
            "jättämisestä. Jos",
            "kauppakirjaan merkitään eräpäivä ja jos rakennustyö tai työvaihe viivästyy "
            "kuukauden tai",
            "enemmän, myyjän on muutettava kauppakirjaan merkittyä eräpäivää viivästystä "
            "vastaavasti",
            "ja ilmoitettava ostajalle uusi eräpäivä kirjallisesti heti, kun viivästyksen "
            "kesto on myyjän",
            "tiedossa.",
            "4 Laskusääntö perustuu asuntokauppalain 4 luvun 29 §:ään, jonka mukaan "
            "toiseksi",
            "viimeinen erä on määrältään vähintään 8 % kauppahinnasta ja viimeinen erä "
            "vähintään 2 %",
            "kauppahinnasta. Jos kauppahinta on pienempi kuin 70 % velattomasta hinnasta,",
            "kauppahintana pidetään eriä laskettaessa rahamäärää, joka vastaa 70 % "
            "velattomasta",
            "hinnasta. Laskusääntö ei vaikuta kauppahinnan määrään. Se vaikuttaa vain "
            "siihen, kuinka",
            "suuri osa kauppahinnasta erääntyy valmistumisvaiheessa.",
            "4 Viivästyskorko ja hyvityskorko",
            "Jos maksuerää ei makseta viimeistään eräpäivänä, ostaja on velvollinen "
            "maksamaan",
            "viivästyneelle määrälle vuotuista viivästyskorkoa eräpäivästä maksupäivään "
            "korkolain",
            "(633/82) 4 §:n 1 momentissa tarkoitetun korkokannan mukaisesti. Maksuerä "
            "katsotaan",
            "määräajassa maksetuksi, kun se on maksettu viimeistään eräpäivänä johonkin "
            "Suomessa",
            "toimivaan talletuspankkiin edellä kohdassa 3. mainitulle tilille.",
            "Jos maksuerä suoritetaan enemmän kuin 7 päivää ennen sen erääntymistä, "
            "ostajalla on",
            "oikeus saada 0 %/v suuruinen hyvityskorko maksupäivän ja eräpäivän väliseltä "
            "ajalta. Katso",
            "kuitenkin mitä kohdissa 3. ja 7. on sanottu viimeisen erän maksamisesta ja "
            "omistusoikeuden",
            "siirtymisestä.",
            "5",
            "5 Asunnon arvioitu valmistumisaika (merkitään selvästi kumpi vaihtoehto "
            "valitaan)",
            "■ Vaihtoehto 1",
            "□ Arvioitu valmistumisaika",
            "31.3.2021",
            "□ Vaihtoehto 2 Asunto valmistuu aikaisintaan ja viimeistään",
            "1.4.2021 31.5.2021",
            "Myyjän on lähetettävä ostajalle kirjallinen ilmoitus asunnon "
            "valmistumispäivästä",
            "viimeistään kuukautta ennen sen valmistumista, jos kauppa on tehty ennen em.",
            "ajankohtaa.",
            "Jäljempänä kohdassa 13. tarkoitettuja myyjän viivästystä koskevia "
            "säännöksiä, lukuun",
            "ottamatta ostajan oikeutta pidättyä maksusta, sovelletaan arvioidun "
            "valmistumisajan osalta",
            "vasta, mikäli asunnon hallinnan luovutus viivästyy arvioidusta "
            "valmistumisajasta enemmän",
            "kuin 30 päivää. Valmistumisajan siirtymisestä myyjän on viipymättä "
            "ilmoitettava kirjallisesti",
            "ostajalle.",
            "■ Vaihtoehto 3",
            "□ Asunto on valmis. Asunnon hallinta luovutetaan ostajalle",
            "30.6.2021",
            "Ostaja vastaa asuntokauppalain 4 luvun 5 §:n mukaisesti hallinnan "
            "luovutuksesta lukien",
            "yhtiövastikkeista ja muista asunnosta aiheutuvista kustannuksista.",
            "6 Ennen valmistumista myydyn asunnon hallinnan luovutus ja",
            "vastikkeenmaksuvelvollisuuden alkaminen",
            "Ostaja saa asunnon hallintaansa heti, kun rakennusvalvontaviranomainen on "
            "hyväksynyt",
            "sen käyttöönotettavaksi, asunnon vastaanottotarkastus on pidetty, "
            "omistusoikeus kaupan",
            "kohteena oleviin osakkeisiin on siirtynyt ja asuntokauppalain 4 luvun 4 §:n "
            "mukaisesti",
            "myyjän kanssa sovitut, valmistuneet ja erääntyneet lisä- ja muutostyöt on "
            "maksettu.",
            "Edellyttäen, että myyjä on ilmoittanut asunnon hallinnan siirtymispäivästä, "
            "ostaja vastaa",
            "asuntokauppalain 4 luvun 5 §:n mukaisesti hallinnan luovutuksesta lukien "
            "yhtiövastikkeista ja",
            "muista asunnosta aiheutuvista kustannuksista.",
            "Jos asunnon hallinnan luovutus viivästyy ostajan puolella olevan seikan "
            "vuoksi, ostaja",
            "vastaa edellä tarkoitetuista maksuista siitä lähtien, kun hallinnan "
            "luovutuksen olisi tämän",
            "kauppasopimuksen mukaan pitänyt tapahtua. Ostajalla ei kuitenkaan ole "
            "velvollisuutta ottaa",
            "vastaan asunnon hallintaa aikaisemmin kuin kuukauden kuluttua siitä, kun "
            "myyjä lähetti",
            "ilmoituksen hallinnan siirtymispäivästä.",
            "6",
            "7 Omistusoikeuden siirtyminen ja osakehuoneistorekisteri-ilmoitukset",
            "Omistusoikeus osakkeisiin siirtyy, kun osakkeiden kauppahinta mahdollisine",
            "viivästyskorkoineen on kokonaisuudessaan maksettu. Jos ostaja ilman myyjän "
            "suostumusta",
            "maksaa viimeisen kauppahintaerän ennen sen eräpäivää, omistusoikeus siirtyy "
            "vasta",
            "viimeisen erän eräpäivänä. Kts. kohta 22 (omistusoikeuden siirtymistä "
            "koskeva ehto, jos",
            "ostajalla on aikaisempi Hitas-asunto)",
            "Ennen omistusoikeuden siirtymistä ostajalla on panttioikeus osakkeisiin "
            "kauppahintaerien",
            "takaisinmaksamisen sekä mahdollisen koron ja vahingonkorvauksen vakuudeksi. "
            "Jos",
            "osakkeet on 10. kohdassa edellytetyin tavoin pantattu, tällä "
            "panttioikeudella on parempi",
            "etuoikeus kuin ostajan panttioikeudella.",
            "Turva-asiakirjojen säilyttäjä huolehtii asuntokauppalain mukaisesti tätä "
            "osakekauppaa",
            "koskevien ilmoitusten tekemisestä osakehuoneistorekisteriin. Säilyttäjä ei "
            "saa ilman myyjän",
            "suostumusta ilmoittaa ostajan saantoa kirjattavaksi "
            "osakehuoneistorekisteriin ennen kuin on",
            "selvitetty, että ostaja on maksanut kauppahinnan sekä suorittanut muut "
            "siihen rinnastettavat",
            "kauppasopimuksen mukaiset velvoitteet ja asuntokauppalain 2 luvun 6 §:n "
            "mukaisesti",
            "myyjän kanssa sovitut, valmistuneet, erääntyneet ja turva-asiakirjan "
            "säilyttäjän tiedossa",
            "olevat lisä- ja muutostyöt on maksettu.",
            "Jos kaupan kohteena oleviin osakkeisiin kohdistuu panttioikeus, ulosmittaus "
            "tai",
            "turvaamistoimenpide, turva-asiakirjojen säilyttäjä tekee niitä koskevat "
            "ilmoitukset",
            "osakehuoneistorekisteriin asuntokauppalain 2 luvun 15 §:ssä tarkoitetun "
            "luettelon tietojen",
            "perusteella ostajan saannon kirjaamisen yhteydessä.",
            "8 Varainsiirtovero",
            "Tästä osakekaupasta maksettavan varainsiirtoveron suorittaa ostaja.",
            "Varainsiirtovero on maksettava kahden kuukauden kuluessa omistusoikeuden "
            "siirtymisestä",
            "9 Turva-asiakirjat",
            "Talo rakennetaan myyjän ostajalle esittämien ja turva-asiakirjojen "
            "säilyttäjälle luovutettujen",
            "turva-asiakirja-asetuksen5 1 §:n mukaisten turva-asiakirjojen ja niiden "
            "liitteiden mukaisesti.",
            "Rakentaminen rahoitetaan tähän kauppakirjaan liitetyn taloussuunnitelman "
            "mukaisesti",
            "(taloussuunnitelman muuttaminen, ks. kohta 11 ).",
            "7",
            "Turva-asiakirjojen ja osakekirjojen säilyttäjä",
            "Ö-Pankki Oyj",
            "Säilytyspaikan osoite, missä turva-asiakirjat ovat ostajan nähtävillä",
            "PL 123, 00020 Ö-Pankki",
            "5 Valtioneuvoston asetus turva-asiakirjoista asuntokaupoissa (835/2005)",
            "10 Kauppakirjaan perustuvien oikeuksien ja velvollisuuksien luovuttaminen ja",
            "panttaaminen",
            "Ostajalla on oikeus, ennen kuin hän on saanut omistusoikeuden osakkeisiin, "
            "luovuttaa",
            "kauppasopimuksen tuottamat oikeudet edelleen. Ellei myyjä anna luovutukseen "
            "kirjallista",
            "suostumustaan, ostaja vastaa luovutuksesta huolimatta myyjälle tähän "
            "kauppakirjaan",
            "perustuvista ostajan velvollisuuksista. Ostajan on välittömästi annettava "
            "tieto luovutuksesta",
            "edellä kohdassa 9. mainitulle turva-asiakirjojen säilyttäjälle ja myyjälle "
            "luovutussopimuksen",
            "kappaleella tai sen oikeaksi todistetulla jäljennöksellä.",
            "Ostajalla on oikeus ilman myyjän suostumusta pantata tähän kauppakirjaan "
            "perustuva",
            "oikeutensa osakkeisiin, asunnon hallintaan ja kaupan ehkä purkautuessa "
            "ostajalle",
            "palautettaviin maksuihin.",
            "Ostajan on välittömästi annettava panttauksesta kirjallisesti tieto "
            "turva-asiakirjojen",
            "säilyttäjälle.",
            "11 Taloussuunnitelman ja yhtiöjärjestyksen muuttaminen",
            "Yhtiö saa rakentamisvaiheen aikana ottaa velkaa, antaa varallisuuttaan "
            "vakuudeksi tai tehdä",
            "muita sitoumuksia vain taloussuunnitelman mukaisesti. Taloussuunnitelmassa "
            "ilmoitettua",
            "velkojen määrää voidaan korottaa tai muita vastuita lisätä ainoastaan "
            "seuraavissa",
            "tapauksissa:",
            "1. Kaikki ostajat suostuvat kirjallisesti muutokseen.",
            "2. Ilman ostajien suostumusta, jos korotus perustuu",
            "a. lain muutoksesta, viranomaisen päätöksestä tai rakennustyötä kohdanneesta",
            "ennalta arvaamattomasta ja ylivoimaisesta esteestä johtuvaan",
            "rakennuskustannusten nousuun, jonka perusteella yhtiö on rakentamista ja",
            "korjausrakentamista koskevan sopimuksen mukaan velvollinen maksamaan",
            "korotetun hinnan;",
            "8",
            "b. sellaiseen laissa sallittuun rahanarvon muutoksen huomioon ottamiseen,",
            "jonka perusteella yhtiö on rakentamista tai korjausrakentamista koskevan",
            "sopimuksen ehtojen mukaan velvollinen maksamaan korotetun hinnan; tai",
            "c. sellaiseen lain muutoksesta tai viranomaisen päätöksestä johtuvaan yhtiön",
            "muiden velvoitteiden lisäykseen, jota ei ole voitu ottaa huomioon",
            "taloussuunnitelmaa laadittaessa.",
            "3. Ilman ostajien suostumusta voidaan yhtiön menoihin lisätä ostajien omiksi",
            "edustajikseen valitsemien rakennustyön tarkkailijan ja tilintarkastajan "
            "palkkiot sekä",
            "muut heidän töistään aiheutuvat kulut, vaikka niitä ei olekaan arvioitu tai "
            "mainittu",
            "taloussuunnitelmassa. (Katso kohta 12)",
            "Taloussuunnitelman muutoksesta ja sen perusteesta on viipymättä ilmoitettava "
            "turva-",
            "asiakirjojen säilyttäjälle ja osakkeenostajille. Suostumusta edellyttävässä "
            "muutoksessa",
            "ilmoitus on tehtävä ennen taloussuunnitelman muutosta edellyttävään "
            "toimenpiteeseen",
            "ryhtymistä.",
            "Taloussuunnitelman muuttaminen ei vaikuta maksettavaan kauppahintaan. Jos "
            "yhtiön",
            "velkojen määrää korotetaan, kohdassa 3. sovittu kaupan kohteena oleviin "
            "osakkeisiin",
            "kohdistuva lainaosuus nousee kuitenkin vastaavasti.",
            "Yhtiöjärjestystä voidaan muuttaa ilman ostajien ja pantinhaltijan "
            "suostumusta vain, jos",
            "muutos ei loukkaa heidän oikeuksiaan ja muuta yhtiön taloudellisen toiminnan "
            "perusteita.",
            "12 Osakkeenostajien kokous, tilintarkastajan ja rakennustyön tarkkailijan "
            "valinta",
            "Yhtiön hallituksen on kutsuttava osakkeenostajien kokous koolle "
            "viivytyksettä sen jälkeen,",
            "kun vähintään yhdestä neljäs-osasta yhtiön asuntoja on tehty "
            "luovutussopimus.",
            "Osakkeenostajilla on oikeus yhtiöjärjestyksen estämättä valita yhtiölle "
            "tilintarkastaja, jonka",
            "toimikausi kestää sen tilikauden loppuun, jolloin rakentamisvaihe päättyy. "
            "Samoin",
            "osakkeenostajilla on oikeus valita rakennustyön tarkkailija, jonka "
            "toimikausi kestää",
            "rakentamisvaiheen loppuun. Tarkkailijalla on oltava tehtävän edellyttämä "
            "ammattipätevyys",
            "eikä hän saa olla riippuvuussuhteessa rakennustyön suorittajaan tai myyjään.",
            "Tilintarkastajan ja rakennustyön tarkkailijan palkkioista vastaa yhtiö, "
            "jonka menoihin palkkiot",
            "sekä muut heidän töistään aiheutuvat kulut saadaan lisätä "
            "taloussuunnitelmasta riippumatta.",
            "13 Asunnon luovutuksen viivästyminen",
            "Jos ostajalla on perusteltu syy olettaa, että asunnon hallinnan luovutus "
            "tulee viivästymään,",
            "ostajalla on oikeus pidättyä kauppahintaerien maksamisesta, kunnes myyjä "
            "saattaa",
            "todennäköiseksi, että hän kykenee täyttämään sopimuksen ajoissa tai että "
            "sopimuksen",
            "täyttämisestä asetettu vakuus riittää turvaamaan ostajan oikeudet. Ostajalla "
            "on oikeus",
            "9",
            "pidättyä maksusta myyjän viivästyksen vuoksi muissakin asuntokauppalain 4 "
            "luvun 7 §:ssä",
            "määritellyissä tilanteissa.",
            "Ostaja saa purkaa kaupan myyjän viivästyksen vuoksi, jos sopimusrikkomus on "
            "olennainen.",
            "Asetettamansa kohtuullisen pituisen lisäajan kuluessa ostaja saa purkaa "
            "kaupan vain, jos",
            "myyjä ilmoittaa, ettei hän täytä sopimusta tämän ajan kuluessa.",
            "Jos myyjä osoittaa, että viivästys johtuu rakennustyötä kohdanneesta, myyjän "
            "ja työhön",
            "osallistuvien urakoitsijoiden sekä näiden käyttämien tavarantoimittajien",
            "vaikutusmahdollisuuksien ulkopuolella olevasta esteestä, jota ei ole "
            "kohtuudella voitu ottaa",
            "huomioon kauppaa tehtäessä ja jonka seurauksia ei kohtuudella voida välttää "
            "tai voittaa,",
            "ostaja ei saa purkaa kauppaa, ellei viivästyksen kesto ylitä 60 päivää. "
            "Mikäli ostaja joutuisi",
            "kohtuuttomaan tilanteeseen, jos hänen olisi pysyttävä sopimuksessa, hän saa "
            "kuitenkin",
            "purkaa kaupan edellä olevan estämättä.",
            "Ostaja ei saa purkaa kauppaa myyjän viivästyksen vuoksi sen jälkeen, kun "
            "asunto on",
            "luovutettu ostajan hallintaan ja turva-asiakirjojen säilyttäjä on "
            "ilmoittanut ostajan saannon",
            "kirjattavaksi osakehuoneistorekisteriin.",
            "Jos ostaja näyttää, että on ennalta painavia syitä olettaa purkuun "
            "oikeuttavan viivästyksen",
            "tapahtuvan, ostaja saa purkaa kaupan jo ennen kuin asunnon sovittu "
            "luovutusajankohta on",
            "käsillä.",
            "Jos myyjä tiedustelee ostajalta, hyväksyykö tämä viivästyksestä huolimatta "
            "määrätyssä",
            "ajassa tapahtuvan sopimuksen täyttämisen eikä ostaja vastaa kohtuullisessa "
            "ajassa",
            "tiedustelun saatuaan, ostaja ei saa purkaa kauppaa, jos myyjä täyttää "
            "sopimuksen",
            "ilmoittamassaan ajassa.",
            "Ostajalla on oikeus korvaukseen myyjän viivästyksen aiheuttamasta vahingosta",
            "asuntokauppalain 4 luvun 11 §:n mukaisesti.",
            "14 Vuositarkastus, virheilmoitukset ja virheen seuraamukset",
            "Myyjä järjestää vuositarkastuksen aikaisintaan 12 kuukauden ja viimeistään "
            "15 kuukauden",
            "kuluttua siitä, kun rakennusvalvontaviranomainen on hyväksynyt rakennuksen",
            "käyttöönotettavaksi. Myyjä ilmoittaa vuositarkastuksen ajankohdasta "
            "kirjallisesti ostajalle",
            "vähintään kuukautta ennen sen järjestämistä. Ostajan on ilmoitettava "
            "vuositarkastuksen",
            "yhteydessä tai viimeistään kolmen viikon kuluessa vuositarkastuksen "
            "pöytäkirjan",
            "tiedoksisaannista niistä virheistä, jotka hän on havainnut tai hänen olisi "
            "pitänyt havaita",
            "viimeistään vuositarkastuksessa. Muutoin ostaja menettää oikeutensa vedota "
            "tällaisiin",
            "virheisiin.",
            "Jos asunnossa ilmenee virhe, jota ostajan ei voida edellyttää havainneen "
            "viimeistään",
            "vuositarkastuksessa, hän menettää oikeutensa vedota virheeseen, jollei hän "
            "ilmoita",
            "10",
            "virheestä ja siihen perustuvista vaatimuksistaan kohtuullisessa ajassa "
            "siitä, kun hän on",
            "havainnut virheen tai hänen olisi pitänyt se havaita.",
            "Ostaja ei saa virheenä vedota seikkaan, josta hänen täytyy olettaa tienneen "
            "kauppaa",
            "tehtäessä. Jos asunto sitä myytäessä on valmis, sovelletaan asunnon "
            "ennakkotarkastuksen",
            "vaikutuksista, mitä asuntokauppalain 6 luvun 12 ja 19",
            "§:ssä säädetään.",
            "Ostajalla on asunnon virheen perusteella oikeus pidättyä maksamasta jäljellä "
            "olevaa osaa",
            "kauppahinnasta. Ostaja ei kuitenkaan saa pidättää rahamäärää, joka "
            "ilmeisesti ylittää ne",
            "vaatimukset, joihin hänellä on virheen perusteella oikeus.",
            "Ostaja voi kohtuullisen ajan kuluessa virheen huomattuaan vaatia virheen "
            "korjaamista tai",
            "oikaisemista, mikäli virheen oikaisemisesta aiheutuvat kustannukset eivät "
            "ole kohtuuttoman",
            "suuret verrattuna virheen merkitykseen ostajalle. Jos virheen oikaisu ei "
            "tule kysymykseen tai",
            "jollei oikaisua suoriteta kohtuullisessa ajassa, ostaja saa vaatia "
            "virheeseen nähden",
            "kohtuullista hinnanalennusta tai, jos sopimusrikkomus on olennainen, purkaa "
            "kaupan.",
            "Myyjällä on oikeus, vaikkei ostaja olisi sitä vaatinutkaan, oikaista virhe "
            "kohtuullisessa ajassa",
            "kustannuksellaan, ellei siitä aiheudu ostajalle olennaista haittaa, asunnon "
            "arvon alenemista",
            "tai vaaraa siitä, että ostajalle aiheutuneet kustannukset jäävät "
            "korvaamatta.",
            "Oikeudesta saada korvausta virheen perusteella säädetään asuntokauppalain 4 "
            "luvun 26",
            "§:ssä. Ostajan ja yhtiön välisestä puhevallan jaosta virhetilanteissa "
            "säädetään",
            "asuntokauppalain 4 luvun 18 a §:ssä.",
            "15 Ostajan sopimusrikkomukset ja niiden seuraukset",
            "Myyjä saa purkaa kaupan ostajan maksuviivästyksen vuoksi, jos "
            "sopimusrikkomus on",
            "olennainen. Jos myyjä tällä perusteella purkaa kaupan (merkittävä kumpi "
            "vaihtoehto",
            "valitaan).",
            "■ Vaihtoehto 1: Myyjällä on oikeus asuntokauppalain 4 luvun 35 §:n 1 "
            "momentin mukaan",
            "□",
            "määräytyvään vahingonkorvaukseen.",
            "□ Vaihtoehto 2: Ostajan on maksettava myyjälle sopimuksen purkamisesta "
            "aiheutuneet",
            "kulut sekä korvauksena myyjälle aiheutuneesta muusta vahingosta 2 % edellä "
            "kohdassa 3",
            "sovitusta velattomasta hinnasta, ellei jompikumpi osapuoli erikseen näytä, "
            "että purkamisesta",
            "aiheutunut vahinko eroaa siitä olennaisesti. Tällöin ostaja korvaa "
            "aiheutuneen vahingon",
            "asuntokauppalain 4 luvun 35 §:n 1 momentin mukaisesti.",
            "Myyjällä on oikeus edellä mainittuun korvaukseen myös, jos ostaja rikkoo "
            "sopimuksen",
            "peruuttamalla kaupan.",
            "11",
            "Myyjällä ei ole kuitenkaan oikeutta korvaukseen, jos ostajan maksuviivästys "
            "tai kaupan",
            "peruuttaminen johtuu lain säännöksestä, yleisen liikenteen tai "
            "maksuliikenteen",
            "keskeytyksestä tai muusta samankaltaisesta esteestä, jota ostaja ei "
            "kohtuudella voi välttää",
            "eikä voittaa.",
            "Vahingonkorvauksen määrää voidaan sovitella, jos maksuviivästys tai kaupan",
            "peruuttaminen johtuu maksuvaikeuksista, joihin ostaja on joutunut sairauden, "
            "työttömyyden",
            "tai muun erityisen seikan vuoksi pääasiassa omatta syyttään.",
            "16 Menettely kaupan purkautuessa",
            "Jos kauppa puretaan tai ostaja rikkoo sopimuksen peruuttamalla kaupan, "
            "myyjän on",
            "palautettava ostajan maksama kauppahinta turva-asiakirjojen säilyttäjälle "
            "ostajan ja",
            "mahdollisten pantinhaltijoiden lukuun. Jos kauppa puretaan, myyjän on "
            "maksettava",
            "palautettavalle kauppahinnalle korkoa korkolain (633/1982) 3 §:n 2 "
            "momentissa tarkoitetun",
            "korkokannan mukaan siitä päivästä lukien, jona myyjä vastaanotti maksun. Jos "
            "kauppa",
            "puretaan sen jälkeen, kun asunto on luovutettu ostajan hallintaan, ostajan "
            "on suoritettava",
            "myyjälle kohtuullinen korvaus asunnosta saamastaan merkittävästä tuotosta "
            "tai hyödystä.",
            "Jos ostaja on pannut asuntoon tarpeellisia tai hyödyllisiä kustannuksia, "
            "myyjän on kaupan",
            "purkamisen yhteydessä suoritettava niistä ostajalle kohtuullinen korvaus.",
            "Jos asunnon kunto on ostajan hallinta-aikana huonontunut enemmän kuin mitä "
            "voidaan",
            "pitää tavanomaisena kulumisena tai jos asunto on tänä aikana vahingoittunut "
            "ja tämä johtuu",
            "huolimattomuudesta ostajan puolelta, ostaja ei saa purkaa kauppaa, ellei hän "
            "korvaa",
            "myyjälle mainitusta syystä johtuvaa arvon alenemista.",
            "Myyjän on ilmoitettava kaupan purusta ja peruuttamisesta turva-asiakirjojen "
            "säilyttäjälle.",
            "17 Vakuudet",
            "Myyjä on asettanut ja luovuttanut turva-asiakirjojen säilyttäjälle yhtiön ja "
            "asunto-",
            "osakkeenostajien hyväksi seuraavat vakuudet.",
            "A) Asuntokauppalain 2 luvun 17 §:n mukainen rakentamisvaiheen vakuus",
            "kiinteistökiinnitys",
            "12",
            "Merkittävä vakuuden laji: pankkitalletus, pankkitakaus tai tarkoitukseen "
            "soveltuva",
            "vakuutus, joka on määrältään aluksi vähintään 5 % yhtiön taloussuunnitelmaan "
            "merkityistä",
            "rakennuskustannuksista ja kulloinkin vähintään 10 % myytyjen "
            "asunto-osakkeiden",
            "kauppahintojen yhteismäärästä. Vakuuden on oltava voimassa vähintään 3 "
            "kuukautta",
            "siitä, kun rakennusvalvontaviranomainen on hyväksynyt rakennuksen "
            "käyttöönotettavaksi.",
            "Rakentamisvaiheen vakuuden lakatessa, myyjä asettaa tilalle "
            "rakentamisvaiheen",
            "jälkeisen vakuuden, joka on määrältään vähintään 2 % myytyjen osakkeiden",
            "kauppahintojen yhteismäärästä. Tämä vakuus on voimassa vähintään 15 "
            "kuukautta sen",
            "jälkeen, kun rakennusvalvontaviranomainen on hyväksynyt rakennuksen",
            "käyttöönotettavaksi. Rakentamisvaiheen jälkeisen vakuuden "
            "asettamisvelvollisuus lakkaa,",
            "kun on kulunut 15 kuukautta rakennuksen käyttöönottohyväksynnästä. Jos "
            "asunto-",
            "osakkeiden kauppahinta on vähemmän kuin 70 % velattomasta hinnasta, "
            "kauppahintana",
            "rakentamisvaiheen ja rakentamisvaiheen jälkeistä vakuutta laskettaessa "
            "pidetään",
            "rahamäärää, joka vastaa 70 % myytyjen osakkeiden velattomasta hinnasta.",
            "Yhtiön ja osakkeenostajien on annettava kirjallinen suostumus vakuuksien",
            "vapauttamiselle, kun perustajaosakas on täyttänyt rakentamista koskevan "
            "sopimuksen ja",
            "asunto-osakkeiden kauppaa koskevien sopimusten mukaiset velvoitteensa. Yhtiö "
            "tai",
            "osakkeenostaja, joka aiheettomasti ja vastoin kuluttajariitalautakunnan6 "
            "suositusta on",
            "kieltäytynyt antamasta suostumusta vakuuden vapauttamiseen, voidaan "
            "velvoittaa",
            "korvaamaan tästä myyjälle aiheutunut vahinko kohtuullisella määrällä.",
            "liman ostajien ja yhtiön antamia suostumuksiakin vakuudet vapautuvat "
            "viimeistään 12",
            "kuukauden kuluttua yhtiön kaikkien rakennusten vuositarkastuksen "
            "pitämisestä, jos",
            "yhtiölle on valittu asuntokauppalain 2 luvun 23 §:ssä tarkoitettu hallitus. "
            "Vakuudet eivät",
            "kuitenkaan vapaudu, jos yhtiö tai asunto-osakkeen ostaja vastustaa "
            "vakuuksien",
            "vapautumista ja saattaa asian hakemuksella kuluttajavalituslautakunnan tai",
            "tuomioistuimen käsiteltäväksi. Vapautumista vastustavan on ilmoitettava "
            "vastustuksestaan",
            "sille vakuuden antajalle tai talletuspankille, joka on vakuudeksi "
            "vastaanottanut",
            "pankkitalletuksen sekä toimitettava tälle kuluttajavalituslautakunnan tai "
            "käräjäoikeuden",
            "antama todistus asian vireille saattamisesta ennen edellä säädetyn määräajan",
            "päättymistä uhalla, että vakuudet muuten vapautuvat.",
            "Merkitään vakuuden antaja tai se talletuspankki, joka on vakuudeksi "
            "vastaanottanut",
            "pankkitalletuksen ja jolle tässä kappaleessa tarkoitettu ilmoitus ja "
            "todistus on toimitettava.",
            "B) Asuntokauppalain 2 luvun 19 §:n mukainen suorituskyvyttömyysvakuus",
            "pankkitalletus 100 € Ä-Pankki Oyj:ssä",
            "13",
            "Merkittävä vakuuden antaja ja vakuuden laji: vakuutus, pankkitakaus tai "
            "Kuluttajaviraston",
            "vahvistamat ehdot täyttävä muu takaus. Vakuus on määrältään 25 % yhtiön",
            "taloussuunnitelman mukaisista rakennuskustannuksista. Vakuus on voimassa 10 "
            "vuotta",
            "siitä, kun rakennusvalvontaviranomainen on hyväksynyt rakennuksen "
            "käyttöönotettavaksi",
            "6 Kuluttajariitalautakunnasta annetun lain (42/1978) 1 §:n mukaan "
            "kuluttajariitalautakunta voi",
            "antaa ratkaisusuosituksia vakuuden käyttöä ja sen vapauttamista koskevissa "
            "yksittäisissä",
            "riita-asioissa riippumatta siitä, kuka riidan osapuolista saattaa asian "
            "lautakunnan",
            "käsiteltäväksi.",
            "18 Myyjän ilmoitusten tiedoksisaanti",
            "Myyjän ostajalle lähettämän kirjallisen ilmoituksen on katsottava saapuneen "
            "ostajalle",
            "viimeistään seitsemäntenä päivänä lähettämisen jälkeen, jos se on lähetetty "
            "ostajan myyjälle",
            "viimeksi ilmoittamaan osoitteeseen.",
            "19 Rakentamista koskevat säännökset ja määräykset",
            "Yhtiölle on haettu rakennuslupaa",
            "1.7.2020",
            "Yhtiö rakennetaan rakennusluvan hakemisajankohtana voimassa olevien "
            "säännösten ja",
            "määräysten tai niihin mahdollisesti myönnettyjen poikkeuslupien mukaisesti.",
            "20 Mikäli laite- tai materiaalitoimittaja on antanut asuntoon kuuluvaan "
            "laitteeseen tai",
            "materiaaliin takuun, myyjä ei vastaa tästä takuusta",
            "21 Erimielisyyksien ratkaiseminen",
            "Jos erimielisyyksiä ei voida ratkaista osapuolten välisellä neuvottelulla, "
            "asia voidaan saattaa",
            "kuluttajariitalautakunnan käsiteltäväksi kuluttajariitalautakunnasta annetun "
            "lain mukaisesti.",
            "Jos erimielisyydet saatetaan tuomioistuimen ratkaistavaksi, kanne on "
            "nostettava vastaajan",
            "kotipaikkakunnan tai asunnon sijaintipaikkakunnan yleisessä alioikeudessa. "
            "Kuluttaja voi",
            "nostaa kanteen myös Suomessa sijaitsevan asuinpaikkansa yleisessä "
            "alioikeudessa.",
            "22 Muut ehdot",
            "Hitas-ehtojen mukaisesti ostaja/ostajatalous ei saa pysyvästi omistaa muita "
            "Hitas-asunto-",
            "osakkeita. (ks. erillinen kauppakirjan Hitas-omistusliite)",
            "Omistusoikeus kaupan kohteena oleviin osakkeisiin siirtyy ostajalle, kun "
            "kauppahinta on",
            "kokonaisuudessaan maksettu ja kun aikaisemmat Hitas-osakkeet on luovutettu",
            "14",
            "omistusoikeudella. Ostaja on velvollinen esittämään luovutuksista "
            "selvityksen myyjälle",
            "asunnon valmistumiseen mennessä.",
            "Myyjällä on oikeus purkaa kauppa, mikäli aikaisempia Hitas-osakkeita ei ole "
            "luovutettu",
            "omistusoikeudella ennen kaupan kohteena olevan asunnon valmistumista. "
            "Myyjällä on",
            "oikeus omistamisrajoituksen rikkomistilanteissa purkaa kauppa kohtuullisen "
            "ajan kuluessa",
            "kuitenkin viimeistään kuuden (6) kuukauden kuluessa kaupan kohteena olevan "
            "asunnon",
            "valmistumisesta.",
            "Erityisistä syistä Asuntopalvelut voi myöntää ostajalle lisäaikaa "
            "aikaisemman asunnon",
            "luovuttamiselle, jolloin myyjän oikeus purkaa kauppa siirtyy vastaavasti.",
            "Muut ehdot",
            "Muita ehtoja ja myös sellasta",
            "15",
            "Muut ehdot jatkuu",
            "Ostajan vakuutus ja kaupanteon yhteydessä luovutetut asiakirjat",
            "Ostajalle on esitetty kauppakirjan kohdassa 9. tarkoitetut turva-asiakirjat. "
            "Tämän",
            "kauppakirjan allekirjoituksella ostaja vakuuttaa huolellisesti tutustuneensa "
            "turva-asiakirjoihin",
            "sekä ilmoittaa hyväksyvänsä tämän kaupan ehdot.",
            "Näiden sopimusehtojen lisäksi kauppaan sovelletaan asuntokauppalakia "
            "(843/1994) ja",
            "valtioneuvoston asetusta turva-asiakirjoista asuntokaupoissa (835/2005).",
            "16",
            "Tämän asiakirjan allekirjoituksella ostaja kuittaa samalla vastaanottaneensa "
            "seuraavat",
            "kaupanteon yhteydessä luovutetut asiakirjat:",
            "ehkä",
            "17",
            "Allekirjoitukset",
            "Tätä kauppakirjaa on tehty kolme samasanaista kappaletta, yksi kummallekin "
            "sopijapuolelle",
            "ja yksi turva-asiakirjojen säilyttäjälle. Myyjä toimittaa välittömästi "
            "kauppakirjakappaleen",
            "turva-asiakirjojen säilyttäjälle.",
            "Paikka ja aika",
            "Mörkökylässä 1.7.2020",
            "Myyjä",
            "Helsingin kaupunki/ Kaupunkiympäristö, asuntotuotanto / Allekirjoitus "
            "oikeaksi todistetaan",
            "Valtakirjalla",
            "Mörkö",
            "Ostaja/ostajat",
            "Matti Meikäläinen & Maija Meikäläinen",
            "Asuntokauppalain edellyttämät vakuudet on asetettu kohdan 17. mukaisesti",
            "Paikka ja aika",
            "Turva-asiakirjojen säilyttäjä",
            "Ö-Pankki Oyj, PL 123, 00020 Ö-Pankki",
            "18",
        ]

    def test_pdf_content_without_id_is_expected(self):
        generated_without_id = remove_pdf_id(self.pdf_content)
        expected_without_id = remove_pdf_id(self.expected_pdf_content)
        if generated_without_id != expected_without_id:
            # Don't assert a == b, because the output is too long to be
            # printed in the test output.
            assert False, "Invalid PDF content"


def read_file(file_name: str) -> bytes:
    with open(my_dir / file_name, "rb") as fp:
        return fp.read()


def write_file(file_name: str, data: bytes) -> None:  # pragma: no cover
    with open(my_dir / file_name, "wb") as fp:
        fp.write(data)
