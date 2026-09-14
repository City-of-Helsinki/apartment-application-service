from django.core.management.base import BaseCommand

from invoicing.drupal_payment_sync import resend_failed_drupal_payment_sync_events


class Command(BaseCommand):
    help = "Move failed Drupal payment outbox events back to pending state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of failed events to reset.",
        )

    def handle(self, *args, **options):
        updated = resend_failed_drupal_payment_sync_events(limit=options["limit"])
        self.stdout.write(f"Reset failed Drupal payment outbox events: {updated}")
