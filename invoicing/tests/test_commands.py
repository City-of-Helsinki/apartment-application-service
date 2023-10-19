from datetime import timedelta
from unittest import mock
from unittest.mock import MagicMock, Mock

import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from django.utils.timezone import localtime

from apartment.tests.factories import ApartmentDocumentFactory
from invoicing.services import (
    TALPA_EMAIL_CONTENT_TEMPLATE,
    TALPA_EMAIL_SUBJECT_TEMPLATE,
)
from invoicing.tests.factories import ApartmentInstallmentFactory
from invoicing.tests.sap.utils import assert_apartment_installment_match_xml_data


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
    added_to_be_sent_but_not_yet_ready = ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=2,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=None,
        due_date=timezone.localdate()
        + timedelta(days=settings.SAP_DAYS_UNTIL_INSTALLMENT_DUE_DATE + 1),
    )
    should_get_sent = ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=3,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=None,
    )
    ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=4,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=timezone.now(),
    )  # already sent to SAP

    def send_xml_to_sap_side_effect(xml, filename=None, timestamp=None):
        return assert_apartment_installment_match_xml_data(should_get_sent, xml)

    # check generated xml and make sure only should_get_sent is included
    send_xml_to_sap.side_effect = send_xml_to_sap_side_effect

    call_command(
        "send_installments_to_sap",
    )

    not_added_to_be_sent.refresh_from_db()
    assert not_added_to_be_sent.sent_to_sap_at is None
    should_get_sent.refresh_from_db()
    assert should_get_sent.sent_to_sap_at is not None
    added_to_be_sent_but_not_yet_ready.refresh_from_db()
    assert added_to_be_sent_but_not_yet_ready.sent_to_sap_at is None


@override_settings(
    MAILER_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TALPA_EMAIL="taplaemail@example.com",
)
@mock.patch("invoicing.services.send_xml_to_sap", autospec=True)
@pytest.mark.django_db
def test_email_notification_after_sending_installments_to_sap(_, freezer):
    apartment = ApartmentDocumentFactory()
    added_to_be_sent_but_not_yet_ready = ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=2,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=None,
        due_date=timezone.localdate()
        + timedelta(days=settings.SAP_DAYS_UNTIL_INSTALLMENT_DUE_DATE + 1),
    )
    should_get_sent = ApartmentInstallmentFactory(
        apartment_reservation__apartment_uuid=apartment.uuid,
        apartment_reservation__list_position=3,
        added_to_be_sent_to_sap_at=timezone.now(),
        sent_to_sap_at=None,
    )

    call_command(
        "send_installments_to_sap",
    )

    should_get_sent.refresh_from_db()
    assert should_get_sent.sent_to_sap_at is not None
    added_to_be_sent_but_not_yet_ready.refresh_from_db()
    assert added_to_be_sent_but_not_yet_ready is not None
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.subject == TALPA_EMAIL_SUBJECT_TEMPLATE.format(
        sender_id=settings.SAP["SENDER_ID"]
    )
    assert m.to == [settings.TALPA_EMAIL]
    assert m.reply_to == [settings.TALPA_EMAIL_REPLY_TO]
    assert m.body == TALPA_EMAIL_CONTENT_TEMPLATE.format(
        sender_id=settings.SAP["SENDER_ID"],
        count=1,
        date_time=localtime(timezone.now()).strftime("%d.%m.%Y %H:%M:%S"),
    )


VALID_TEST_PAYMENT_DATA = """022121917199          12800     0000000000000000000000000000000000000000000000000000000000
300000010700152221218221218730000077                           SAP ATestaaj1 00006658100  
300000010700152221218221218730000077                           SAP BTestaaj1 00006658101  
900000200001331620000000000000000000000000000000000000000000000000000000000000000000000000
"""  # noqa: E501, W291


@mock.patch("paramiko.SFTPClient.from_transport")
@mock.patch("paramiko.Transport")
@pytest.mark.django_db
def test_fetch_payments_from_sap(_, paramiko_sftp):
    installment = ApartmentInstallmentFactory(invoice_number=730000077)

    mock_sftp = MagicMock()
    mock_sftp.listdir = Mock(return_value=["MR_TESTING_123.TXT"])

    def mock_getfo(_, local_file):
        local_file.write(VALID_TEST_PAYMENT_DATA.encode("utf-8"))

    mock_sftp.getfo = Mock(side_effect=mock_getfo)
    paramiko_sftp.return_value = mock_sftp

    call_command(
        "fetch_payments_from_sap",
    )

    mock_sftp.rename.assert_called_with("MR_TESTING_123.TXT", "arch/MR_TESTING_123.TXT")
    assert installment.payments.count() == 2
