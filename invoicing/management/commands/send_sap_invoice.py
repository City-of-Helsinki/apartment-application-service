import logging
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from os import path
from xml.etree.ElementTree import tostring

from invoicing.models import ApartmentInstallment
from invoicing.sap.xml import generate_xml

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send invoice XML to SAP via FTP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reference_number",
            help="Send invoice by using reference number of invoice",
        )
        parser.add_argument(
            "--create_xml_file_only_to",
            help="Create only XML file to specified path",
            nargs="?",
            const="",
        )

    def handle(self, *args, **options):
        if options["reference_number"]:
            reference_number = options["reference_number"]
            apartment_installment = ApartmentInstallment.objects.get(
                reference_number=reference_number
            )
        else:
            return

        xml_content = generate_xml([apartment_installment])

        if options["create_xml_file_only_to"]:
            file_name = datetime.now().strftime("%Y%m%d%H%M%S") + ".xml"
            file_path = options["create_xml_file_only_to"]
            full_path = path.join(file_path, file_name)
            with open(full_path, "w") as f:
                xml_content_string = tostring(
                    xml_content, encoding="unicode", xml_declaration=True
                )
                f.write(xml_content_string)
