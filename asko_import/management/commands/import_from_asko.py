"""
Import data from AsKo CSV files.
"""
from django.core.management.base import BaseCommand

from ...importer import run_asko_import


class Command(BaseCommand):
    help = __doc__.lstrip().splitlines()[0]

    def handle(
        self,
        import_directory,
        commit=False,
        ignore_errors=False,
        flush=False,
        flush_all=False,
        *args,
        **kwargs
    ):
        run_asko_import(
            import_directory,
            commit,
            ignore_errors,
            flush,
            flush_all,
        )

    def add_arguments(self, parser):
        parser.add_argument("import_directory", metavar="IMPORT_DIRECTORY")
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--ignore-errors", action="store_true")
        parser.add_argument("--flush", action="store_true")
        parser.add_argument("--flush-all", action="store_true")
