import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from application_form.services.export import ApartmentSalesDataExportService


class Command(BaseCommand):
    help = (
        "Exports a machine-readable CSV of apartment sales data, one apartment per "
        "row, without personal data. Currently covers every apartment in projects "
        "that have unsold apartments. Written to "
        "settings.APARTMENT_DATA_TRANSFER_PATH by default."
    )

    default_file_name_format = "apartment_sales_data_"

    def add_arguments(self, parser):
        parser.add_argument(
            "--filename",
            help=(
                "Filename for the export file. Default is "
                f"{self.default_file_name_format}YYYYMMDDHHMMSS.csv"
            ),
        )
        parser.add_argument(
            "--output-dir",
            default=settings.APARTMENT_DATA_TRANSFER_PATH,
            help="Directory to write the file to "
            "(default: settings.APARTMENT_DATA_TRANSFER_PATH)",
        )
        parser.add_argument(
            "--print",
            action="store_true",
            help="Print the CSV to stdout instead of writing a file",
        )

    def handle(self, *args, **options):
        service = ApartmentSalesDataExportService()
        rows = service.get_rows()
        csv_string = service._make_csv(rows)

        if options["print"]:
            self.stdout.write(csv_string, ending="")
            return

        filename = options.get("filename") or (
            f"{self.default_file_name_format}"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        )
        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, filename)

        with open(path, encoding=service.FILE_ENCODING, mode="w", newline="") as f:
            f.write(csv_string)

        self.stdout.write(
            f"Exported {len(rows) - 1} apartments from {service.project_count} "
            f"projects to {path}"
        )
