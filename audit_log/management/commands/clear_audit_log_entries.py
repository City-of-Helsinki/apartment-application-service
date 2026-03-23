from logging import getLogger

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Clear AuditLog which is already sent to Elasticsearch,"
        "only clear if settings.CLEAR_AUDIT_LOG_ENTRIES is set to True (default: False)"
    )

    def handle(self, *args, **options):
        if settings.CLEAR_AUDIT_LOG_ENTRIES:
            logger.info("Clearing sent resilient audit log entries")
            call_command("clear_sent_entries")
