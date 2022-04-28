import pytest
from django.core.management import call_command
from django.utils import timezone
from os import listdir, path
from unittest import mock

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
    ApartmentInstallmentFactory()  # not added to be sent to SAP
    should_get_sent = ApartmentInstallmentFactory(
        added_to_be_sent_to_sap_at=timezone.now()
    )
    ApartmentInstallmentFactory(
        added_to_be_sent_to_sap_at=timezone.now(), sent_to_sap_at=timezone.now()
    )  # already sent to SAP

    send_xml_to_sap.side_effect = (
        # only should_get_sent should get sent
        lambda xml: assert_apartment_installment_match_xml_data(should_get_sent, xml)
    )

    call_command(
        "send_pending_installments_to_sap",
    )
