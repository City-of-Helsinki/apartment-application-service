import datetime
import pathlib
import unittest
from decimal import Decimal

import pytest

from apartment_application_service.pdf import PDFCurrencyField as CF
from users.tests.factories import UserFactory

from ..pdf.haso import (
    create_haso_contract_pdf_from_data,
    HasoContractPDFData,
)
from .pdf_utils import (
    get_cleaned_pdf_texts,
    remove_pdf_id,
    set_up_contract_pdf_test_data,
)

# This variable should be normally False, but can be set temporarily to
# True to override the expected test result PDF file.  This is useful
# when either the template has changed or the test data has changed and
# a new expected result PDF file needs to be generated.  Remember to
# revert this variable back to False to ensure that the test is
# actually testing the expected result.
OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE = False

my_dir = pathlib.Path(__file__).parent


CONTRACT_PDF_DATA = HasoContractPDFData(
    occupant_1="Asta Asukas",
    occupant_1_signing_text="Asta Asukas",
    occupant_1_street_address="Astankuja 12a5",
    occupant_1_phone_number="040 123 4567",
    occupant_1_email="asta.asukas@esimerkki.fi",
    occupant_1_ssn="190395-999X",
    occupant_2="Bertta Asukas",
    occupant_2_signing_text="Bertta Asukas",
    occupant_2_street_address="Bertankaari 8 C 12",
    occupant_2_phone_number="050 987 6543",
    occupant_2_email="bertta.asukas@toinen.fi",
    occupant_2_ssn="240900A8883",
    right_of_residence_number="1234",
    project_housing_company="Lämmin Koti Oy",
    project_street_address="Lämpimäntie 9 00100 Helsinki",
    apartment_number="C 12",
    apartment_structure="4h+k+s",
    living_area=125.3,
    floor=77,
    right_of_occupancy_payment=CF(cents=4521400, suffix=" €"),
    payment_due_date=datetime.date(2020, 8, 19),
    installment_amount=CF(euros=Decimal("46537.45")),
    right_of_occupancy_fee=CF(cents=78950, suffix=" € / kk"),
    right_of_occupancy_fee_m2=CF(cents=1011, suffix=" € /m\u00b2/kk"),
    project_contract_apartment_completion="31.3.2021 — 31.5.2021",
    signing_place_and_time="Helsinki 19.8.2020",
    project_acc_salesperson="Maija Myyjä",
    project_contract_other_terms="Kaikenlaisia ehtoja",
    project_contract_usage_fees="400 € / kk",
    project_contract_right_of_occupancy_payment_verification="Tarkistusta",
    approval_date="1.7.2020",
    approver="Helsingin kaupunki",
    alterations="1200,00",
    index_increment=Decimal("123.45"),
)


class TestHasoContractPdfFromData(unittest.TestCase):
    def setUp(self) -> None:
        pdf = create_haso_contract_pdf_from_data(CONTRACT_PDF_DATA)
        self.pdf_content = pdf.getvalue()

        if OVERRIDE_EXPECTED_TEST_RESULT_PDF_FILE:
            write_file("haso_contract_test_result.pdf", self.pdf_content)
            assert False, "Not testing, because PDF file was overridden."

        self.expected_pdf_content = read_file("haso_contract_test_result.pdf")

        return super().setUp()

    def test_pdf_content_is_not_empty(self):
        assert self.pdf_content

    @pytest.mark.django_db
    def test_payment_recipient_field_goes_on_pdf(self):

        pass

    @pytest.mark.django_db
    def test_salesperson_signing_info_is_formatted_correctly(self):
        """Assert that the chosen salesperson's name and signing time/place get passed
        correctly to the HASO contract PDF generation.
        Small test mainly for TDD purposes."""

        salesperson = UserFactory(first_name="Markku", last_name="Myyjä")
        paid_place = "Helsinki"
        paid_time = "10.9.2025"

        pdf_data = set_up_contract_pdf_test_data(
            salesperson=salesperson,
            sales_price_paid_place=paid_place,
            sales_price_paid_time=paid_time,
        )

        assert pdf_data.signing_place_and_time == "Helsinki 10.9.2025"
        assert pdf_data.project_acc_salesperson == "Markku Myyjä"
        pass

    def test_pdf_content_text_is_correct(self):
        # acquire a new version of this PDF array by running
        # python manage.py pdf_as_array application_form/tests/haso_contract_test_result.pdf  # noqa: E501
        assert get_cleaned_pdf_texts(self.pdf_content) == [
            "Helsinki Haso",
            "Asumisoikeussopimus",
            "1 Sopijapuolet",
            "Talonomistajan nimi Osoite",
            "Helsingin Asumisoikeus Oy PL 58226, 00099 Helsingin kaupunki",
            "Puhelin Henkilötunnus tai Y-tunnus",
            "Y-0912770-2",
            "Asumisoikeuden haltijan 1 nimi Asumisoikeuden haltijan 2 nimi",
            "Asta Asukas Bertta Asukas",
            "Osoite 1 Osoite 2",
            "Astankuja 12a5 Bertankaari 8 C 12",
            "Puhelin 1 Puhelin 2",
            "040 123 4567 050 987 6543",
            "Sähköposti 1 Sähköposti 2",
            "asta.asukas@esimerkki.fi bertta.asukas@toinen.fi",
            "Henkilötunnus 1 Henkilötunnus 2",
            "190395-999X 240900A8883",
            "Asumisoikeuden hyväksyjä Hyväksymispäivämäärä",
            "Helsingin kaupunki 1.7.2020",
            "Järjestysnumero",
            "1234",
            "1",
            "2 Sopimuksen kohde",
            "Asumisoikeuden haltija saa asumisoikeuden perusteella yksinomaiseen käyttöönsä",
            "seuraavat huonetilat.",
            "Asumisoikeuskohteen nimi",
            "Lämmin Koti Oy",
            "Asumisoikeuskohteen osoite Huoneiston numero",
            "Lämpimäntie 9 00100 C 12",
            "Helsinki",
            "Huoneiston osoite (jos poikkeaa asumisoikeuskohteen osoitteesta)",
            "Huoneistotyyppi (huoneluku) Huoneiston pinta-ala m2 1)",
            "4h+k+s 125.3",
            "Sijaintikerros",
            "77",
            "1) Huoneiston pinta-alalla tarkoitetaan sitä asumisoikeuden haltijan yksinomaisessa",
            "käytössä olevaa lattiapinta-alaa, jota rajoittavat huoneistoa ympäröivien seinien",
            "sisäpinnat. Siihen ei kuitenkaan lueta kuuluviksi hormiryhmien, putkikanavien, pilarien,",
            "kantavien seinien, kylmien kuistien, tuulikaappien eikä portaiden vaatimaa alaa portaiden",
            "lähtökerroksessa eikä kellari- ja ullakkotiloja, kahdelle tai useammalle asunnolle yhteisesti",
            "kuuluvaa eteistä, käytävää, WC:tä, pesu- tai kylpyhuonetta, keittiötä tai näihin verrattavaa",
            "muuta yhteiskäyttöön tarkoitettua, asumiseen liittyvää tilaa. Huoneiston pinta-alaa",
            "laskettaessa ei ole otettu lukuun sitä osaa lattiapinta-alasta, jonka kohdalla sisäkaton",
            "korkeus lattiasta on pienempi kuin 160 cm. Huoneiston pinta-alaa yksittäistapauksissa",
            "määrättäessä voidaan muillakin kuin edellä lausutuilla osin käyttää RT-kortiston tai",
            'kiinteistönhoitotiedoston ohjekorttia "Rakennuksen pinta-alat" (SFS 5139-slandardi).',
            "2",
            "3 Asumisoikeudesta perittävä asumisoikeusmaksu 2)",
            "3.1 Asumisoikeuden ensimmäinen haltija",
            "Asumisoikeustalon rakentamisvaiheesta perittävä asumisoikeusmaksu",
            "45 214,00 €",
            "Indeksikorotus Lisä- ja muutostyöt",
            "123,45 1200,00",
            "Asumisoikeusmaksu erääntyy maksettavaksi seuraavan maksuaikataulun mukaisesti",
            "Eränumero Eräpäivämäärä Rakentamisvaihe tai muu Maksuerän suuruus",
            "maksuajankohdan peruste",
            "1. erä",
            "19.8.202 46 537,45",
            "0",
            "2. erä",
            "3. erä",
            "Viivästyskorko",
            "Jos maksuerää ei makseta viimeistään eräpäivänä, ostaja on velvollinen maksamaan",
            "viivästyneelle määrälle vuotuista viivästyskorkoa eräpäivästä maksupäivään korkolain",
            "(633/82) 4 §:n 1 momentissa tarkoitetun korkokannan mukaisesti.",
            "2) Kun asumisoikeus perustetaan, oikeuden saajan on maksettava talon omistajalle",
            "asumisoikeusmaksu. Lisäksi asumisoikeuden haltijan on maksettava käyttövastiketta siten",
            "kuin asumisoikeusasunnoista annetussa laissa (393/2021) säädetään. Ehto, jonka mukaan",
            "asumisoikeuden edellytykseksi tai asumisoikeuden perusteella asetetaan asumisoikeuden",
            "haltijalle muu kuin asumisoikeusasunnoista annetussa laissa (393/2021) tarkoitettu",
            "maksuvelvollisuus on mitätön.",
            "3",
            "3.2 Asumisoikeuden myöhempi haltija",
            "3.2.1. Vastikkeellinen saanto",
            "3.2.1.1. Asumisoikeuden enimmäishinta 3)",
            "Kunnan vahvistama asumisoikeuden enimmäishinta",
            "Kunnan päätös",
            "Asumisoikeusmaksu rakentamisvaiheesta",
            "Tarkistus",
            "□ erääntynyt",
            "□ ei erääntynyt",
            "Asumisoikeusmaksulle, sen erääntymisestä tähän päivään saakka",
            "rakennuskustannusindeksin muutoksen mukaan laskettu indeksikorotus 4)",
            "Luovuttajan tai häntä edeltäneiden asumisoikeuden haltijoiden huoneistoon tekemien tai",
            "hallinta-aikanaan rahoittamien kohtuullisten parannusten arvo luovutushetkellä",
            "3) Asumisoikeuden luovutus- tai lunastushinta ei saa ylittää asumisoikeusasunnoista",
            "annetun lain (393/2021) 56 §:n mukaan määräytyvää enimmäishintaa, jonka kunta",
            "vahvistaa. Sitoumus on siltä osin mitätön kuin luovutushinta ylittää sallitun enimmäishinnan.",
            "4) Jos asumisoikeusmaksu suoritetaan erinä, indeksin muutos lasketaan ensimmäisen erän",
            "eräpäivästä.",
            "4",
            "3.2.1.2. Asumisoikeudesta sovittu luovutus- tai lunastushinta 5)",
            "Asumisoikeudestaan asumisoikeuden haltija suorittaa",
            "□ talonomistajalle",
            "□ luovuttajalle",
            "Luovutushinta",
            "Luovutus on",
            "□ kokonaan vastikkeellinen",
            "□ osittain vastikkeellinen",
            "Asumisoikeusmaksun maksaminen",
            "□ Asumisoikeudesta suoritettavat maksut kuitataan kokonaisuudessaan suoritetuksi",
            "tämän asumisoikeussopimuksen allekirjoituksin.",
            "□ Asumisoikeudesta suoritettavasta maksusta kuitataan tämän",
            "sopimuksen allekirjoituksin maksetuksi € ja loppuosa erääntyy",
            "maksettavaksi seuraavan maksuaikataulun mukaan.",
            "□ Asumisoikeusmaksu erääntyy maksettavaksi seuraavan maksuaikataulun mukaan.",
            "(Kts myös kohta 9.1)",
            "Eränumero Eräpäivämäärä Maksuajankohdan peruste Maksuerän suuruus",
            "1. erä",
            "2. erä",
            "3. erä",
            "Viivästyskorko",
            "Erääntyneille maksuille suoritetaan korkolain (633/82) 4 §:n mukaan määräytyvää korkoa.",
            "5",
            "Merkitään, että asumisoikeus on edellä mainitun vastikkeen suorittamisen lisäksi saatu",
            "□ osittain lahjana",
            "□ perintönä",
            "□ testamenttina",
            "□ puolisoiden omaisuuden osituksessa tai erottelussa",
            "□ yhteisomistussuhteen purkamisessa",
            "Luovuttaja",
            "Luovutus",
            "Luovutusajankohta",
            "5) Asumisoikeudenluovutus- tai lunastushinta ei saa ylittää asumisoikeusasunnoista annetun",
            "lain (393/2021) 56 §:n mukaan määräytyvää enimmäishintaa, jonka kunta vahvistaa.",
            "Sitoumus on siltä osin mitätön kuin luovutushinta ylittää sallitun enimmäishinnan.",
            "3.2.2 Vastikkeeton saanto",
            "Merkitään, että asumisoikeudesta ei ole suoritettu vastiketta ja se on kokonaan saatu",
            "□ lahjana",
            "□ perintönä",
            "□ testamenttina",
            "□ puolisoiden omaisuuden osituksessa tai erottelussa",
            "□ yhteisomistussuhteen purkamisessa",
            "Luovuttaja",
            "Luovutus",
            "Luovutusajankohta",
            "6",
            "4 Käyttövastike ja sen suorittaminen 6)",
            "Asumisoikeuden haltijat sitoutuvat maksamaan talonomistajalle käyttövastiketta (arvio",
            "käyttövastikkeesta sisään muuttaessa ks. 9.2 Muut ehdot).",
            "€/kk /m2/kk",
            "789,50 € / kk 10,11 € /m²/kk",
            "Lämmityskustannukset sisältyvät käyttövastikkeeseen",
            "Asumisoikeuden haltijat ovat velvollisia suorittamaan lisäksi seuraavia käyttökorvauksia",
            "400 € / kk",
            "Käyttövastikkeen maksupäivä Pankkitili, jolle käyttövastike maksetaan",
            "kuukauden 5. päivä isännöitsijä ilmoittaa myöhemmin",
            "Käyttövastikkeen määräytyminen (asumisoikeusasunnoista annetun lain 32 § ja 33 §)",
            "1. Asumisoikeuden haltijalta voidaan periä käyttövastiketta",
            "2. Käyttövastikkeen suuruuden tulee määräytyä niin, että vastiketuloilla voidaan kattaa",
            "yhteisöön kuuluvien asumisoikeusasuntojen ja niihin liittyvien tilojen rahoituksen ja",
            "ylläpidon edellyttämät, kohtuullisen taloudenhoidon mukaiset menot",
            "3. Käyttövastikkeen voidaan sopia määräytyvän niin, että erilaisia menoeriä varten on",
            "eri maksuperuste, kuten huoneiston pinta-alan taikka veden, sähkön tai muun",
            "hyödykkeen todellinen kulutus tai käyttö",
            "4. Käyttövastike ei saa olla paikkakunnalla käyttöarvoltaan samanveroisista",
            "huoneistoista yleensä perittäviä vuokria korkeampi",
            "5. Asuntorahasto voi vahvistaa käyttövastikkeita määrättäessä noudatettavat yleiset",
            "perusteet",
            "Käyttövastikkeen korottaminen (asumisoikeusasunnoista annetun lain 38 §)",
            "1. Milloin talon omistaja haluaa korottaa käyttövastiketta, hänen on ilmoitettava",
            "asumisoikeuden haltijalle siitä kirjallisesti",
            "2. Samalla on ilmoitettava korotuksen peruste ja uusi käyttövastike",
            "3. Korotettu käyttövastike tulee voimaan aikaisintaan kahden kuukauden kuluttua",
            "ilmoituksen tekemistä lähinnä seuraavan käyttövastikkeen maksukauden alusta",
            "4. Erikseen ei kuitenkaan tarvitse ilmoittaa lämmöstä, vedestä tai muusta huoneiston",
            "käyttöön kuuluvasta etuudesta suoritettavasta korvauksen sellaisesta korotuksesta,",
            "joka perustuu kulutuksen kasvuun tai huoneistossa asuvien henkilöiden lukumäärän",
            "7",
            "lisääntymiseen, jos etuus on sovittu korvattavaksi erikseen kulutuksen tai",
            "huoneistossa asuvien henkilöiden lukumäärän perusteella",
            "5. Kunkin maksukauden kulutuksen määrä on ilmoitettava asumisoikeuden haltijalle",
            "6) Käyttövastike on maksettava viimeistään toisena päivänä käyttövastikkeen maksukauden",
            "alusta lukien, jollei maksuajasta ole toisin sovittu. Käyttövastikkeen maksukautena pidetään",
            "kuukautta tai muuta ajanjaksoa, jolta käyttövastike sopimuksen mukaan on maksettava.",
            "Ehto, jonka mukaan asumisoikeuden haltijan on suoritettava käyttövastiketta ennakolta, on",
            "mitätön. Kt. asumisoikeusasunnoista annetun lain 32 §, 39 § ja 40 §.",
            "5 Asumisoikeuden kohteena olevien huoneiston ja muiden tilojen",
            "kunto",
            "□ Huoneisto ja muut tilat luovutetaan siinä kunnossa, missä ne luovutushetkellä ovat",
            "□ Talonomistaja sitoutuu suorittamaan ilman eri korvausta huoneistossa tai muissa",
            "asumisoikeuden kohteena olevissa tiloissa korjaukset",
            "Mihin mennessä",
            "Mitkä korjaukset",
            "6 Asumisoikeuden kohteena olevien huoneiston ja muiden tilojen",
            "hallinnan luovutus",
            "Asumisoikeuden haltija saa hallintaansa asumisoikeuden kohteena olevan huoneiston ja",
            "muut tilat arviolta (pvm).",
            "31.3.2021 — 31.5.2021",
            "Tarkka muuttopäivä ilmoitetaan 3 kuukautta ennen muuttoa. Tarkat muuttoon liittyvät ohjeet",
            "lähetetään n. 6 viikkoa ennen muuttopäivää.",
            "7 Vakuuden asettaminen",
            "Asumisoikeussopimusta tehtäessä tai sopimusehtoja muutettaessa, asumisoikeuden haltijan",
            "vaihtuessa tai näihin verrattavissa tilanteissa voidaan sopia, että asumisoikeuden haltija",
            "8",
            "asettaa vakuuden sen vahingon varalta, joka talonomistajalle voi aiheutua siitä, että",
            "asumisoikeuden haltija laiminlyö velvollisuutensa asumisoikeuden haltijana. Jos sovittua",
            "vakuutta ei sovitussa ajassa aseteta, sopimus voidaan purkaa.",
            "Vakuutena asumisoikeuden haltija luovuttaa Helsingin Asumisoikeus Oy haltuun",
            "500,00 € suuruisen rahasumman. Vakuus tulee olla maksettuna avainten luovutukseen",
            "mennessä. Isännöintitoimisto lähettää vastikevakuuslaskut.",
            "8 Asumisoikeuden haltijan osallistuminen asumisoikeustalon",
            "hallintoon ja päätöksen tekoon",
            "Tämän asumisoikeussopimuksen perusteella asumisoikeuden haltija ja hänen kanssaan",
            "asumisoikeusasunnossa asuvat saavat oikeuden osallistua asumisoikeustaloaan",
            "koskevaan hallintoon ja päätöksentekoon vähintään siinä laajuudessa kuin laissa",
            "yhteishallinnosta vuokrataloissa (649/90) säädetään.",
            "□ Asumisoikeuden haltijalla on lisäksi oikeus",
            "□ Asumisoikeuden haltijalla ja hänen kanssaan asuvalla on lisäksi oikeus",
            "9 Lisäksi on sovittu",
            "9.1 Rakentamisvaiheesta perittävän asumisoikeusmaksun tarkistus",
            "Jos Asumisen rahoitus- ja kehittämiskeskus Ara tarkistaa hyväksymäänsä",
            "asuntolainoituksen perusteena olevaa hankinta-arvo-osuutta, talonomistaja voi tarkistaa",
            "asumisoikeusmaksua enintään määrällä, joka vastaa asumisoikeusmaksun osuutta",
            "hankinta-arvo-osuuden tarkistuksesta. Asumisoikeusmaksun tarkistusta voi vaatia",
            "maksettavaksi aikaisintaan kahden viikon kuluttua siitä, kun asumisoikeusmaksun",
            "tarkistuksesta ja sen määrästä on kirjallisesti ilmoitettu asumisoikeuden haltijalle.",
            "Asumisoikeusmaksun tarkistuksesta on asumisoikeuden haltijalle ilmoitettava viimeistään",
            "vuoden kuluessa asuntohallituksen tarkistamispäätöksen tekemisestä.",
            "Tarkistusta",
            "9",
            "9.2. Muut ehdot ja sopimuksenteon yhteydessä asiakkaalle luovutetut",
            "asiakirjat",
            "Kaikenlaisia ehtoja",
            "10",
            "Tähän sopimukseen perustuvan asumisoikeuden siirto tai muu luovutus samoin kuin",
            "asumisoikeuden nojalla haltuun saadun koko huoneiston hallinnan luovuttaminen tai",
            "huoneiston hallinnan jakaminen, huoneiston yhteiskäyttö tai sen osan luovuttaminen toiselle",
            "henkilölle määräytyy asumisoikeusasunnoista annetun lain 393/2021 mukaan. Tähän",
            "sopimukseen perustuvan asumisoikeuden pääoma-arvon panttauksesta säädetään edellä",
            "mainitun lain 58 §:ssa.",
            "Jos puolisot käyttävät asumisoikeuden nojalla hallittua huoneistoa yhteisenä asuntonaan, he",
            "vastaavat yhteisvastuullisesti asumisoikeusso pimuksesta johtuvista velvollisuuksista.",
            "Puoliso, joka ei ole asumisoikeussopimuksen osapuoli, vastaa toisen puolison muutettua",
            "huoneis tosta edelleen asumisoikeussopimuksesta johtuvien velvollisuuksien täyttämisestä",
            "niin kauan kuin hän asuu huoneistossa. Puolisoon rinnas tetaan henkilö, jonka kanssa",
            "asumisoikeuden haltija elää avioliiton omaisessa suhteessa. Ks. asumisoikeusasunnoista",
            "annetun 8 §.",
            "Asumisoikeuden lakkaamisesta huoneiston tuhouduttua tai viranomaisen kiellettyä",
            "huoneiston käyttämisen asuntona säädetään asumisoikeusasunnoista annetun lain 29 §.",
            "Tähän sopimukseen perustuva asumisoikeus voi päättyä myös sen johdosta, että",
            "talonomistaja purkaa asumisoikeussopimuksen. Talonomistajan oikeudesta purkaa",
            "asumisoikeussopimus säädetään mainitun lain 68-73§ ja 100 §. Eräissä tapauksissa on",
            "sopimuksen purkamisesta sopimusrikkomuksen johdosta varoitettava ennen kuin sopimus",
            "voidaan purkaa.",
            "Purkamalla sopimus voi päättyä jopa välittömästi. Talon omistajan on annettava",
            "asumisoikeuden haltijalle kirjallinen purkamisilmoitus. Muuttopäivä asumisoikeussopimuksen",
            "päättyessä sopimuksen purkamisen johdosta on sopimuksen päättymispäivää lähinnä",
            "seuraava arkipäivä. Muuttopäivänä asumisoikeuden haltijan on jätettävä puolet huoneistosta",
            "talonomistajan käytettäväksi sekä ennen muuttopäivää lähinnä seuraavan kolmannen",
            "päivän loppua luovutettava huoneisto kokonaan tämän hallintaan.",
            "11",
            "Allekirjoitukset",
            "Tätä sopimusta on tehty kaksi samasanaista kappaletta, toinen talonomistajalle ja toinen",
            "asumisoikeuden haltijalle/haltijoille.",
            "Paikka ja aika",
            "Helsinki 19.8.2020",
            "Talonomistaja",
            "Helsingin Asumisoikeus Oy",
            "Valtakirjalla",
            "Maija Myyjä",
            "Asumisoikeuden haltija 1",
            "Asta Asukas",
            "Asumisoikeuden haltija 2",
            "Bertta Asukas",
            "12",
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
