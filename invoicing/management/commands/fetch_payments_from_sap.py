from django.core.management.base import BaseCommand
from logging import getLogger

from invoicing.services import fetch_payments_from_sap

logger = getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch installment payments from SAP"

    def handle(self, *args, **options):
        logger.info("Fetching payments from SAP...")
        num_of_payments, num_of_files = fetch_payments_from_sap()
        logger.info(
            f"{num_of_payments} payments(s) in {num_of_files} files(s) fetched from SAP"
        )
