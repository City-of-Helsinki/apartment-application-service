from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from io import BytesIO
from os import path

from invoicing.models import ApartmentInstallment
from invoicing.sap.sftp import sftp_put_file_object
from invoicing.sap.xml import generate_installments_xml


class Command(BaseCommand):
    help = "Send invoice XML to SAP via SFTP. FOR TESTING PURPOSES ONLY."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reference_numbers",
            help="Send invoice using comma-separated reference numbers of invoices",
        )
        parser.add_argument(
            "--create_xml_file_only_to",
            help="Create only XML file to specified path",
            nargs="?",
            const="",
        )

    def handle(self, *args, **options):
        installments = ApartmentInstallment.objects.exclude(due_date=None)

        if reference_numbers := options["reference_numbers"]:
            self.stdout.write(f"Reference_numbers: {reference_numbers}")
            if reference_numbers == "__all__":
                apartment_installments = list(installments.all())
            else:
                apartment_installments = list(
                    installments.filter(
                        reference_number__in=[
                            r.strip() for r in reference_numbers.split(",")
                        ]
                    )
                )
        else:
            try:
                apartment_installments = [installments[0]]
            except IndexError:
                apartment_installments = None

        if not apartment_installments:
            self.stdout.write("No matching installments.")
            return

        self.stdout.write(f"Sending installments {apartment_installments}")
        self.stdout.write("---")
        xml_str = generate_installments_xml(apartment_installments).decode("utf-8")
        self.stdout.write("XML content:")
        self.stdout.write(xml_str)
        self.stdout.write("---")
        filename = (
            "MR_IN_ID066_2800_" + timezone.now().strftime("%Y%m%d%H%M%S") + ".xml"
        )
        if options["create_xml_file_only_to"]:
            file_path = options["create_xml_file_only_to"]
            full_path = path.join(file_path, filename)
            self.stdout.write(f"Writing XML file {full_path}")
            with open(full_path, "w") as f:
                f.write(xml_str)
        else:
            self.stdout.write(f"Sending XML as file f{filename} to SFTP")
            sftp_put_file_object(
                settings.SAP_SFTP_HOST,
                settings.SAP_SFTP_USERNAME,
                settings.SAP_SFTP_PASSWORD,
                BytesIO(bytes(xml_str, encoding="utf-8")),
                filename,
                port=settings.SAP_SFTP_PORT,
            )
