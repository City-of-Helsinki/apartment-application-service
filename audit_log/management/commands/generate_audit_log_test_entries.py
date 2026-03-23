from django.core.management.base import BaseCommand, CommandError

from audit_log.audit_logging import log
from audit_log.enums import Operation


class Command(BaseCommand):
    help = "Generate synthetic audit log entries for development testing."

    def add_arguments(self, parser):
        """Add command-line arguments for test-entry generation."""
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of synthetic entries to create (must be > 0).",
        )

    def handle(self, *args, **options):
        """Create synthetic resilient audit-log entries for local testing."""
        count = options["count"]
        if count <= 0:
            raise CommandError("Count must be a positive integer.")

        for _ in range(count):
            log(actor=None, operation=Operation.READ, target=None)

        self.stdout.write(
            self.style.SUCCESS(f"Created {count} audit log test entries.")
        )
