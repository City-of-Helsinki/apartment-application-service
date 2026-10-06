from django.core.management.base import BaseCommand

from invoicing.drupal_payment_sync import dispatch_drupal_payment_sync_events


class Command(BaseCommand):
    help = "Send pending Drupal payment outbox events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Maximum number of outbox events to process.",
        )

    def handle(self, *args, **options):
        processed = dispatch_drupal_payment_sync_events(
            batch_size=options["batch_size"],
        )
        self.stdout.write(f"Processed Drupal payment outbox events: {processed}")
