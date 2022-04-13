import pytest
from django.core.management import call_command
from os import listdir, path

from invoicing.tests.factories import ApartmentInstallmentFactory
from invoicing.tests.sap.utils import assert_apartment_installment_match_xml_data


@pytest.mark.django_db
def test_send_sap_invoice_create_only_file(tmp_path):
    apartment_installment = ApartmentInstallmentFactory()

    call_command(
        "send_sap_invoice",
        reference_number=apartment_installment.reference_number,
        create_xml_file_only_to=tmp_path,
    )

    assert len(listdir(tmp_path)) == 1

    xml_file = listdir(tmp_path)[0]
    full_xml_path = path.join(tmp_path, xml_file)
    with open(full_xml_path, "r") as f:
        xml_content = f.read()

    assert_apartment_installment_match_xml_data(apartment_installment, xml_content)
