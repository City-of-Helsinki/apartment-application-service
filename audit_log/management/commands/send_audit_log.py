from logging import getLogger

from django.conf import settings
from django.core.management import BaseCommand

from audit_log.tasks import send_audit_log_to_elastic_search

logger = getLogger(__name__)


class Command(BaseCommand):
    help = "Send AuditLog to centralized log center"

    def handle(self, *args, **options):

        if settings.ENABLE_SEND_AUDIT_LOG:
            logger.info("Sending audit log to ES")
            sent_count = send_audit_log_to_elastic_search()
            logger.info(f"{sent_count} audit log entries sent to ES")
