from django.core.management.base import BaseCommand

from invoicing.services import send_xml_to_sap


class Command(BaseCommand):
    help = (
        "Send a SAP XML file to the SAP SFTP server. "
        "Meant for testing and exceptional situations."
    )

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str)

    def handle(self, *args, **options):
        self.stdout.write(
            f"Sending XML file {options['filename']} " f"to the SAP SFTP server"
        )
        with open(options["filename"], "rb") as xml_file:
            send_xml_to_sap(bytes(xml_file.read()), options["filename"])
