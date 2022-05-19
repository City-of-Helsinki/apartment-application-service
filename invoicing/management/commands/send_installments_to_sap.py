from django.core.management.base import BaseCommand

from invoicing.services import send_needed_installments_to_sap


class Command(BaseCommand):
    help = "Send needed (marked to be sent and due date close enough) installments to SAP."  # noqa: E501

    def handle(self, *args, **options):
        self.stdout.write("Sending installments to SAP...")
        num_of_installments = send_needed_installments_to_sap()
        self.stdout.write(f"{num_of_installments} installment(s) sent to SAP")
