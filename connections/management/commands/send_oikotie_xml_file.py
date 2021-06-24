import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from django_oikotie.oikotie import send_items

from connections.models import MappedApartment
from connections.oikotie.services import (
    create_xml_apartment_file,
    create_xml_housing_company_file,
    fetch_apartments_for_sale,
)
from connections.utils import create_elastic_connection

_logger = logging.getLogger(__name__)
create_elastic_connection()


class Command(BaseCommand):
    help = (
        "Generate apartments and housing companies XML files to be shown in Oikotie "
        "and send them via FTP"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--only_create_files",
            action="store_true",
            help="Only create XML files without sending them via FTP",
        )
        parser.add_argument(
            "--send_only_type",
            type=int,
            choices=[1, 2],
            help="Send either housing company file (1) or apartment file (2)",
        )

    def handle(self, *args, **options):
        path = settings.APARTMENT_DATA_TRANSFER_PATH
        apartments, housing_companies = fetch_apartments_for_sale()
        sending_apartments = False
        oikotie_files = []

        if not options["send_only_type"] or options["send_only_type"] == 1:
            oikotie_files.append(create_xml_housing_company_file(housing_companies))

        if not options["send_only_type"] or options["send_only_type"] == 2:
            sending_apartments = True
            oikotie_files.append(create_xml_apartment_file(apartments))

        if options["only_create_files"]:
            _logger.info("Not sending XML files to Oikotie")
            return

        for oikotie_file in oikotie_files:
            if oikotie_file:
                try:
                    send_items(path, oikotie_file)
                    _logger.info(
                        f"Successfully sent XML file {path}/{oikotie_file} to Oikotie "
                        "FTP server"
                    )
                except Exception as e:
                    _logger.error(
                        f"File {path}/{oikotie_file} sending via FTP to Oikotie "
                        "failed:",
                        str(e),
                    )
                    raise e

        if sending_apartments:
            MappedApartment.objects.exclude(
                pk__in=[item.key for item in apartments]
            ).update(mapped_oikotie=False)

            for item in apartments:
                MappedApartment.objects.update_or_create(
                    apartment_uuid=item.key,
                    defaults={"mapped_oikotie": True},
                )
