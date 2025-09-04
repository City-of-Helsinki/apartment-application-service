from django.core.management.base import BaseCommand, CommandError
from application_form.tests.pdf_utils import get_cleaned_pdf_texts


class Command(BaseCommand):
    help = """Dumps the pdf file as a Python array. That can be used for updating the test assertions in application_form/tests/test_pdf_hitas.py and application_form/tests/test_pdf_haso.py"""  # noqa: E501

    def add_arguments(self, parser):
        parser.add_argument(
            "pdf_path",
            type=str,
            help="""Path to pdf file.
            Most likely application_form/tests/haso_contract_test_result.pdf
            or application_form/tests/hitas_contract_test_result.pdf""",
        )

    def handle(self, *args, **options):
        pdf_path = options["pdf_path"]

        try:
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()
        except FileNotFoundError:
            raise CommandError(f"No pdf file found at {pdf_path}")

        pdf_lines = get_cleaned_pdf_texts(pdf_content)
        print("\n", pdf_lines)
