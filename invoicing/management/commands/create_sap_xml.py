from django.core.management.base import BaseCommand

from invoicing.models import ApartmentInstallment
from invoicing.sap.xml import generate_installments_xml
from invoicing.services import generate_sap_xml_filename


class Command(BaseCommand):
    help = (
        "Create a SAP XML file of installments. "
        "Meant for testing and exceptional situations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "reference_numbers",
            nargs="*",
            type=str,
            help="Reference numbers of the installments to be included. "
            "If omitted, all pending installments will be used.",
        )

    def handle(self, *args, **options):
        installments_with_due_date = ApartmentInstallment.objects.exclude(due_date=None)

        if reference_numbers := options["reference_numbers"]:
            installments = installments_with_due_date.filter(
                reference_number__in=reference_numbers
            )
        else:
            installments = installments_with_due_date.sap_pending()

        if not installments.exists():
            self.stdout.write("No matching installments.")
            return

        self.stdout.write(
            f"Generating a SAP XML of {installments.count()} installment(s)"
        )

        xml_str = generate_installments_xml(installments).decode("utf-8")
        xml_filename = generate_sap_xml_filename()

        self.stdout.write(f"Writing XML file {xml_filename}")
        with open(xml_filename, "w") as f:
            f.write(xml_str)
