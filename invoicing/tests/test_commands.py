import pytest
from django.core.management import call_command
from django.utils import timezone
from os import listdir, path
from unittest import mock

from apartment.tests.factories import ApartmentDocumentFactory
from invoicing.tests.factories import ApartmentInstallmentFactory
from invoicing.tests.sap.utils import assert_apartment_installment_match_xml_data


@pytest.mark.django_db
def test_send_sap_invoice_create_only_file(tmp_path):
    apartment_installment = ApartmentInstallmentFactory()

    call_command(
        "send_sap_invoice",
        reference_numbers=apartment_installment.reference_number,
        create_xml_file_only_to=tmp_path,
    )

    assert len(listdir(tmp_path)) == 1

    xml_file = listdir(tmp_path)[0]
    full_xml_path = path.join(tmp_path, xml_file)
    with open(full_xml_path, "r") as f:
        xml_content = f.read()

    assert_apartment_installment_match_xml_data(apartment_installment, xml_content)


@mock.patch("invoicing.services.send_xml_to_sap", autospec=True)
@pytest.mark.django_db
def test_pending_installments_to_sap(send_xml_to_sap):
    apartment = ApartmentDocumentFactory()

    not_added_to_be_sent = ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=1,
        added_to_be_sent_to_sap_at=None,
        sent_to_sap_at=None,
    )
    should_get_sent = ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=2,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=None,
    )
    ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=3,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=timezone.now(),
    )  # already sent to SAP

    send_xml_to_sap.side_effect = (
        # check generated xml and make sure only should_get_sent is included
        lambda xml: assert_apartment_installment_match_xml_data(should_get_sent, xml)
    )

    call_command(
        "send_pending_installments_to_sap",
    )

    not_added_to_be_sent.refresh_from_db()
    assert not_added_to_be_sent.sent_to_sap_at is None
    should_get_sent.refresh_from_db()
    assert should_get_sent.sent_to_sap_at is not None
