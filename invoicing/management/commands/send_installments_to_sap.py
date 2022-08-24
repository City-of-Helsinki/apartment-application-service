from django.conf import settings
from django.core.management.base import BaseCommand
from logging import getLogger

from invoicing.services import (
    send_email_notification_to_talpa,
    send_needed_installments_to_sap,
)

logger = getLogger(__name__)


class Command(BaseCommand):
    help = "Send needed (marked to be sent and due date close enough) installments to SAP."  # noqa: E501

    def handle(self, *args, **options):
        logger.info("Sending installments to SAP...")
        num_of_installments, timestamp = send_needed_installments_to_sap()
        logger.info(f"{num_of_installments} installment(s) sent to SAP")
        if settings.TALPA_EMAIL:
            sent_count = send_email_notification_to_talpa(
                num_of_installments, timestamp
            )
            if sent_count > 0:
                logger.info(
                    f"An email notification has been sent to {settings.TALPA_EMAIL}"
                )
            else:
                logger.warning("Failed to send email notification to Talpa")
