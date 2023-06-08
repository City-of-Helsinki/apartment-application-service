from datetime import datetime
from io import BytesIO
from logging import getLogger

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.utils.timezone import localtime

from audit_log import audit_logging
from audit_log.enums import Operation
from invoicing.models import ApartmentInstallment
from invoicing.sap.fetch import (
    process_payment_data,
    SapPaymentDataAlreadyProcessedError,
)
from invoicing.sap.fetch.sftp import SFTPConnection
from invoicing.sap.send.sftp import sftp_put_file_object
from invoicing.sap.send.xml import generate_installments_xml

logger = getLogger(__name__)


TALPA_EMAIL_SUBJECT_TEMPLATE = "{sender_id} aineisto"
TALPA_EMAIL_CONTENT_TEMPLATE = (
    "{sender_id} myyntireskontra-aineistoa lähetetty {count} kpl {date_time}"
)


def send_needed_installments_to_sap() -> (int, datetime):
    installments = ApartmentInstallment.objects.sending_to_sap_needed()
    logger.debug(f"Installment IDs: {[i.pk for i in installments]}")
    num_of_installments = installments.count()
    timestamp = timezone.now()
    if num_of_installments:
        xml = generate_installments_xml(installments)
        logger.debug(f"Generated XML:\n{xml.decode('utf-8')}")
        send_xml_to_sap(xml, timestamp=timestamp)
        installments.set_sent_to_sap_at()
        for installment in installments:
            audit_logging.log(None, Operation.UPDATE, installment)
    return num_of_installments, timestamp


def fetch_payments_from_sap() -> (int, int):
    with SFTPConnection() as sftp_connection:
        filenames = [
            filename
            for filename in sftp_connection.get_filenames()
            if filename.upper().endswith(".TXT")
        ]
        logger.debug(f"Filenames: {filenames}")

        num_of_payments = 0
        num_of_files = 0
        for filename in filenames:
            try:
                payment_data_file = sftp_connection.get_file(filename)
                num_of_payments += process_payment_data(payment_data_file, filename)
            except SapPaymentDataAlreadyProcessedError:
                logger.warning(f'Payment data file "{filename}" already processed')
            except Exception as e:  # noqa
                logger.exception(f'Error handling payment data file "{filename}": {e}')
                continue
            else:
                num_of_files += 1

            try:
                sftp_connection.rename_file(filename, f"arch/{filename}")
            except Exception as e:  # noqa
                logger.exception(f'Error renaming payment data file "{filename}": {e}')

    return num_of_payments, num_of_files


def send_email_notification_to_talpa(count: int, timestamp: datetime):
    email = EmailMessage(
        subject=TALPA_EMAIL_SUBJECT_TEMPLATE.format(
            sender_id=settings.SAP["SENDER_ID"]
        ),
        body=TALPA_EMAIL_CONTENT_TEMPLATE.format(
            sender_id=settings.SAP["SENDER_ID"],
            count=count,
            date_time=localtime(timestamp).strftime("%d.%m.%Y %H:%M:%S"),
        ),
        to=[settings.TALPA_EMAIL],
        reply_to=[settings.TALPA_EMAIL_REPLY_TO],
    )
    return email.send()


def generate_sap_xml_filename(timestamp: datetime) -> str:
    return (
        settings.SAP_SFTP_SEND_FILENAME_PREFIX
        + f"{timestamp.strftime('%Y%m%d%H%M%S')}"
        + ".xml"
    )


def send_xml_to_sap(
    xml: bytes, filename: str = None, timestamp: datetime = None
) -> None:
    if filename is None:
        if timestamp is None:
            timestamp = datetime.now()
        filename = generate_sap_xml_filename(timestamp)
    logger.debug(
        f"Sending XML file {filename} "
        f"to {settings.SAP_SFTP_SEND_HOST}:{settings.SAP_SFTP_SEND_PORT}"
    )
    sftp_put_file_object(
        settings.SAP_SFTP_SEND_HOST,
        settings.SAP_SFTP_SEND_USERNAME,
        settings.SAP_SFTP_SEND_PASSWORD,
        BytesIO(xml),
        filename,
        settings.SAP_SFTP_SEND_PORT,
    )
