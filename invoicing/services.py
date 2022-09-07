from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.utils.timezone import localtime
from io import BytesIO
from logging import getLogger

from audit_log import audit_logging
from audit_log.enums import Operation
from invoicing.models import ApartmentInstallment
from invoicing.sap.sftp import sftp_put_file_object
from invoicing.sap.xml import generate_installments_xml

logger = getLogger(__name__)


TALPA_EMAIL_SUBJECT_TEMPLATE = "{sender_id} aineisto"
TALPA_EMAIL_CONTENT_TEMPLATE = (
    "{sender_id} myyntireskontra-aineistoa lähetetty {count} kpl {date_time}"
)


def send_needed_installments_to_sap() -> int:
    installments = ApartmentInstallment.objects.sending_to_sap_needed()
    logger.debug(f"Installment IDs: {[i.pk for i in installments]}")
    num_of_installments = installments.count()
    timestamp = timezone.now()
    if num_of_installments:
        xml = generate_installments_xml(installments)
        logger.debug(f"Generated XML:\n{xml.decode('utf-8')}")
        send_xml_to_sap(xml, timestamp)
        installments.set_sent_to_sap_at()
        for installment in installments:
            audit_logging.log(None, Operation.UPDATE, installment)
    return num_of_installments, timestamp


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
        settings.SAP_SFTP_FILENAME_PREFIX
        + f"{timestamp.strftime('%Y%m%d%H%M%S')}"
        + ".xml"
    )


def send_xml_to_sap(
    xml: bytes, filename: str = None, timestamp: datetime = None
) -> None:
    if filename is None:
        filename = generate_sap_xml_filename(timestamp)
    logger.debug(
        f"Sending XML file {filename} "
        f"to {settings.SAP_SFTP_HOST}:{settings.SAP_SFTP_PORT}"
    )
    sftp_put_file_object(
        settings.SAP_SFTP_HOST,
        settings.SAP_SFTP_USERNAME,
        settings.SAP_SFTP_PASSWORD,
        BytesIO(xml),
        filename,
        settings.SAP_SFTP_PORT,
    )
