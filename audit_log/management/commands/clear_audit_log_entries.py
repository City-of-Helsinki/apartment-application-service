from django.conf import settings
from django.core.management.base import BaseCommand
from logging import getLogger

from audit_log.tasks import clear_audit_log_entries

logger = getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Clear AuditLog which is already sent to Elasticsearch,"
        "only clear if settings.CLEAR_AUDIT_LOG_ENTRIES is set to True (default: False)"
    )

    def handle(self, *args, **options):
        if settings.CLEAR_AUDIT_LOG_ENTRIES:
            deleted, deleted_count = clear_audit_log_entries()
            if deleted:
                logger.info(f"{deleted_count} audit log entries sent to ES")
            else:
                logger.warning("Something wrong, cannot delete audit log entries")
