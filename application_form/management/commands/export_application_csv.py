from datetime import date, datetime
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from connections.utils import create_elastic_connection
from django.db.models.manager import BaseManager

import django
from typing import List
from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartment
from application_form.models import Application, ApplicationApartment
import csv
import os

_logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = f"""Creates a list of applications with various filters
            and generates a CSV file to the directory
            '{settings.APARTMENT_DATA_TRANSFER_PATH}'
            (defined at settings.APARTMENT_DATA_TRANSFER_PATH)"""

    date_format_human_readable = "YYYY-MM-DD"
    default_file_name_format = "application_csv_export_"
    date_string = datetime.now().strftime("%Y%m%d%H%M%S")
    default_file_name = f"{default_file_name_format}{date_string}.csv"

    updated_at_start: date | None = None
    updated_at_end: date | None = None

    created_at_start: date | None = None
    created_at_end: date | None = None

    def add_arguments(self, parser):

        parser.add_argument(
            "--filename",
            help=f"Filename for the export file. Default filename is in the format {self.default_file_name_format}YYYMMDDHHMMSS.csv",  # noqa:E501
            default=self.default_file_name
        )

        parser.add_argument(
            "--updated_at_start",
            help=f"Start date for when application was last updated ({self.date_format_human_readable})",  # noqa:E501
        )
        parser.add_argument(
            "--updated_at_end",
            help=f"End date for when application was last updated ({self.date_format_human_readable})",  # noqa:E501
        )
        parser.add_argument(
            "--created_at_start",
            help=f"Start date for when application was created ({self.date_format_human_readable})",  # noqa:E501
        )
        parser.add_argument(
            "--created_at_end",
            help=f"End date for when application was created ({self.date_format_human_readable})",  # noqa:E501
        )

        parser.add_argument(
            "--project_address",
            help="The address line of the project, e.g. 'Street road 123', wildcard search, case sensitive",  # noqa:E501
        )

        parser.add_argument(
            "--delimiter",
            help="Delimiter to use in CSV, default is ';'",
            default=";"
        )

    def handle(self, *args, **kwargs):

        # updated_at_start: date|None = None
        # updated_at_end: date|None  = None

        # created_at_start: date|None  = None
        # created_at_end: date|None  = None

        # project_address: str = kwargs.get("project_address")

        # filename:str = kwargs.get("filename", self.default_file_name)

        # if kwargs.get("updated_at_start"):
        #     updated_at_start = datetime.strptime(
        #         kwargs["updated_at_start"], "%Y-%m-%d"
        #     ).date()

        # if kwargs.get("updated_at_end"):
        #     updated_at_end = datetime.strptime(
        #         kwargs["updated_at_end"], "%Y-%m-%d"
        #     ).date()

        # if kwargs.get("created_at_start"):
        #     created_at_start = datetime.strptime(
        #         kwargs["created_at_start"], "%Y-%m-%d"
        #     ).date()

        # if kwargs.get("created_at_end"):
        #     created_at_end = datetime.strptime(
        #         kwargs["created_at_end"], "%Y-%m-%d"
        #     ).date()

        filename: str = kwargs.get("filename", self.default_file_name)

        application_apartments = self.fetch_application_apartments(kwargs)

        rows = self.generate_rows(application_apartments)

        write_path = os.path.join(settings.APARTMENT_DATA_TRANSFER_PATH, filename)
        with open(write_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            for row in rows:
                writer.writerow(row)
                pass

        print(f"Exported {len(rows)} rows to {write_path}")
        pass

    def get_options(self, options):
        self.project_address: str = options.get("project_address")
        if options.get("updated_at_start"):
            self.updated_at_start = datetime.strptime(
                options["updated_at_start"], "%Y-%m-%d"
            ).date()

        if options.get("updated_at_end"):
            self.updated_at_end = datetime.strptime(
                options["updated_at_end"], "%Y-%m-%d"
            ).date()

        if options.get("created_at_start"):
            self.created_at_start = datetime.strptime(
                options["created_at_start"], "%Y-%m-%d"
            ).date()

        if options.get("created_at_end"):
            self.created_at_end = datetime.strptime(
                options["created_at_end"], "%Y-%m-%d"
            ).date()

    def fetch_application_apartments(self, options) -> BaseManager[ApplicationApartment]:  # noqa: E501

        self.get_options(options)

        create_elastic_connection()

        apartments = ApartmentDocument.search()
        if self.project_address:
            apartments = apartments.query(
                "wildcard",
                apartment_address__keyword=f"*{self.project_address}*",
            )

        apartments.execute()
        apt_uuids = [x.uuid for x in apartments.scan()]

        applications = Application.objects.all()

        if self.updated_at_start and self.updated_at_end:
            applications = applications.filter(
                updated_at__gte=self.updated_at_start,
                updated_at__lte=self.updated_at_end,
            ).distinct()
        elif ((not self.updated_at_start and self.updated_at_end) or 
              (self.updated_at_start and not self.updated_at_end)):
            raise ValueError("--updated_at_start and --updated_at_end need to be both defined")

        if self.created_at_start and self.created_at_end:
            applications = applications.filter(
                created_at__gte=self.created_at_start,
                created_at__lte=self.created_at_end,
            ).distinct()
        elif ((not self.created_at_start and self.created_at_end) or 
                (self.created_at_start and not self.created_at_end)):
            raise ValueError("--created_at_start and --created_at_end need to be both defined")

        if self.project_address:
            applications = applications.filter(
                application_apartments__apartment_uuid__in=apt_uuids,
            )

        application_apartments = ApplicationApartment.objects.filter(
            application__in=applications
        ).order_by("apartment_uuid")

        return application_apartments


    def generate_rows(self, application_apartments):

        rows: List[List] = [[
            "Hakemus päivitetty",
            "Kohteen osoite",
            "Asunto",
            "Ensisijainen hakija etunimi",
            "Ensisijainen hakija sukunimi",
            "Ensisijainen hakija syntymäaika",
            "Ensisijainen hakija osoite",
            "Ensisijainen hakija postinumero",
            "Ensisijainen hakija postitoimipaikka",
            "Ensisijainen hakija sähköposti",
            "Kanssahakija etunimi",
            "Kanssahakija sukunimi",
            "Kanssahakija syntymäaika",
            "Kanssahakija osoite",
            "Kanssahakija postinumero",
            "Kanssahakija postitoimipaikka",
            "Kanssahakija sähköposti",
        ]]

        for application_apartment in application_apartments:
            try:
                apartment = get_apartment(application_apartment.apartment_uuid, include_project_fields=True)
            except django.core.exceptions.ObjectDoesNotExist:
                continue

            application = application_apartment.application
            primary_applicant = [app for app in application.applicants.all() if app.is_primary_applicant][0]
            secondary_applicant = None

            row = [
                application.updated_at.strftime("%d.%m.%Y %H:%M:%S"),
                apartment.project_street_address,
                apartment.apartment_number,
                primary_applicant.first_name,
                primary_applicant.last_name,
                primary_applicant.date_of_birth,
                primary_applicant.street_address,
                primary_applicant.postal_code,
                primary_applicant.city,
                primary_applicant.email,
            ]

            if application.applicants_count > 1:
                secondary_applicant = [app for app in application.applicants.all() if not app.is_primary_applicant][0]
                row += [
                    secondary_applicant.first_name,
                    secondary_applicant.last_name,
                    secondary_applicant.date_of_birth,
                    secondary_applicant.street_address,
                    secondary_applicant.city,
                    secondary_applicant.postal_code,
                    secondary_applicant.email,
                ]

            rows.append(row)
        
        return rows
