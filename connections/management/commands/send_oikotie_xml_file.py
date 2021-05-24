import logging
from django.core.management.base import BaseCommand
from django_oikotie.oikotie import send_items

from connections.oikotie.services import (
    create_xml_apartment_file,
    create_xml_housing_company_file,
    fetch_apartments_for_sale,
)
from connections.utils import create_elastic_connection

_logger = logging.getLogger(__name__)
create_elastic_connection()


class Command(BaseCommand):  # pragma: no cover
    help = "Generate apartments and housing companies XML files to be shown in Oikotie \
and send them via FTP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only_create_files",
            action="store_true",
            help="Only create XML files without sending them via FTP",
        )

    def handle(self, *args, **options):
        apartments, housing_companies = fetch_apartments_for_sale()
        path, apartment_file = create_xml_apartment_file(apartments)
        path, housing_file = create_xml_housing_company_file(housing_companies)

        if not options["only_create_files"] and apartment_file and housing_file:
            for f in [apartment_file, housing_file]:
                try:
                    send_items(path, f)
                    _logger.info(
                        f"Succefully sent XML file {path}/{f} to Oikotie FTP server"
                    )
                except Exception as e:
                    _logger.error(
                        f"File {path}/{f} sending via FTP to Oikotie failed:",
                        str(e),
                    )
                    raise e
        else:
            _logger.info("Not sending XML files to Oikotie")
