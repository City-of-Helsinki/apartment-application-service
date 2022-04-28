from django.conf import settings
from django.utils import timezone
from io import BytesIO

from invoicing.models import ApartmentInstallment
from invoicing.sap.sftp import sftp_put_file_object
from invoicing.sap.xml import generate_installments_xml


def send_pending_installments_to_sap() -> QuerySet[ApartmentInstallment]:
    installments = ApartmentInstallment.objects.sap_pending()
    xml = generate_installments_xml(installments)
    send_xml_to_sap(xml)
    installments.set_send_to_sap_at()
    return installments


def send_xml_to_sap(xml: bytes) -> None:
    filename = (
        settings.SAP_SFTP_FILENAME_PREFIX + f"{timezone.now().strftime('%Y%m%d%H%M%S')}"
    )
    sftp_put_file_object(
        settings.SAP_SFTP_HOST,
        settings.SAP_SFTP_USERNAME,
        settings.SAP_SFTP_PASSWORD,
        BytesIO(xml),
        filename,
        settings.SAP_SFTP_PORT,
    )
