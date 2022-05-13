import logging
from django.core.management.base import BaseCommand

from invoicing.services import send_pending_installments_to_sap

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send pending installments to SAP."

    def handle(self, *args, **options):
        logger.info("Sending pending installments to SAP...")
        num_of_installments = send_pending_installments_to_sap()
        logger.info(f"{num_of_installments} installment(s) sent to SAP")
