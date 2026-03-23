from logging import getLogger

from django.conf import settings
from django.core.management import BaseCommand, call_command

logger = getLogger(__name__)


class Command(BaseCommand):
    help = "Send AuditLog to centralized log center"

    def handle(self, *args, **options):

        if settings.ENABLE_SEND_AUDIT_LOG:
            logger.info("Submitting resilient audit log entries to target(s)")
            # Log the number of unsent audit log entries before submission.
            from resilient_logger.models import ResilientLogEntry

            unsent_count = ResilientLogEntry.objects.filter(is_sent=None).count()
            logger.info(f"Number of unsent audit log entries: {unsent_count}")
            import ipdb; ipdb.set_trace()
            call_command("submit_unsent_entries")
