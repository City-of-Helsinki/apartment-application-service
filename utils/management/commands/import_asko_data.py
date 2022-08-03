from django.core.management.base import BaseCommand

from asko_import import run_asko_import


class Command(BaseCommand):
    help = (
        "Import data from AsKo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
        )
        parser.add_argument(
            '--ignore_errors',
            action='store_true',
        )
        parser.add_argument(
            '--directory',
            nargs=1,
            type=str
        )

    def handle(self, *args, **options):
        run_asko_import(**options)
