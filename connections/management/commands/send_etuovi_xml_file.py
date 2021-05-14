import logging
from django.core.management.base import BaseCommand
from django_etuovi.etuovi import send_items

from connections.models import MappedApartment
from connections.etuovi.services import create_xml, fetch_apartments_for_sale
from connections.utils import create_elastic_connection

_logger = logging.getLogger(__name__)
create_elastic_connection()


class Command(BaseCommand):
    help = "Generate apartments XML file to be shown in Etuovi and send it via FTP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only_create_file",
            action="store_true",
            help="Only create XML file without sending it via FTP",
        )

    def handle(self, *args, **options):
        items = fetch_apartments_for_sale()
        path, xml_file = create_xml(items)

        if not options["only_create_file"] and xml_file:
            try:
                send_items(path, xml_file)
                _logger.info(
                    f"Succefully sent Etuovi XML file {path}/{xml_file} to Etuovi FTP \
                        server"
                )
            except Exception as e:
                _logger.error(
                    f"File {path}/{xml_file} sending via FTP to Etuovi failed:", str(e)
                )
                raise e

            for item in items:
                MappedApartment.objects.update_or_create(
                    apartment_uuid=item.cust_itemcode,
                    defaults={"mapped_etuovi": True},
                )
        else:
            _logger.info("Not sending XML file to Etuovi")
