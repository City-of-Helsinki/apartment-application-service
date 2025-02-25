import csv
import operator
from abc import abstractmethod
from io import StringIO

from django.db.models import Max, QuerySet

from apartment.elastic.queries import (
    get_apartment,
    get_apartment_project_uuid,
    get_apartment_uuids,
    get_project,
)
from apartment.enums import ApartmentState
from apartment.utils import get_apartment_state_from_apartment_uuid
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation, LotteryEvent
from application_form.utils import get_apartment_number_sort_tuple


def _get_reservation_cell_value(column_name, apartment=None, reservation=None):
    if not reservation:
        return ""

    # Apartment fields
    if (
        column_name
        in [
            "project_street_address",
            "project_postal_code",
            "project_city",
            "apartment_number",
            "apartment_structure",
            "living_area",
            "floor",
        ]
        and apartment is not None
    ):
        return getattr(apartment, column_name)
    # Profile fields
    if column_name.startswith("primary") or column_name.startswith("secondary"):
        if (
            column_name.startswith("secondary")
            and reservation.customer.secondary_profile is None
        ):
            return None
        else:
            return operator.attrgetter(column_name)(reservation.customer)
    if column_name == "has_children":
        return bool(reservation.has_children)
    if column_name == "lottery_position":
        return reservation.application_apartment.lotteryeventresult.result_position
    if column_name == "queue_position":
        return reservation.queue_position
    if column_name == "right_of_residence":
        return reservation.right_of_residence
    return ""


class CSVExportService:
    CSV_DELIMITER = ";"
    FILE_ENCODING = "utf-8-sig"
    COLUMNS = []

    @abstractmethod
    def get_rows(self):
        pass

    @abstractmethod
    def get_row(self, *args, **kwargs):
        pass

    def _get_header_row(self):
        return [col[0] for col in self.COLUMNS]

    def write_csv_file(self, path):
        csv_string = self.get_csv_string()
        with open(path, encoding=self.FILE_ENCODING, mode="w") as f:
            f.write(csv_string)

    def get_csv_string(self):
        return self._make_csv(self.get_rows())

    def _make_csv(self, lines):
        if len(lines) == 0:
            return ""

        io = StringIO()
        csv_writer = csv.writer(
            io, delimiter=self.CSV_DELIMITER, quoting=csv.QUOTE_NONNUMERIC
        )
        for line in lines:
            csv_writer.writerow(line)

        return io.getvalue()


class ApplicantMailingListExportService(CSVExportService):
    COLUMNS = [
        ("Asunnon numero", "apartment_number"),
        ("Sijainti jonossa", "queue_position"),
        ("Ensisijainen hakija etunimi", "primary_profile.first_name"),
        ("Ensisijainen hakija sukunimi", "primary_profile.last_name"),
        ("Ensisijainen hakija sähköposti", "primary_profile.email"),
        ("Ensisijainen hakija osoite", "primary_profile.street_address"),
        ("Ensisijainen hakija postinumero", "primary_profile.postal_code"),
        ("Ensisijainen hakija postitoimipaikka", "primary_profile.city"),
        (
            "Ensisijainen hakija henkilötunnus",
            "primary_profile.national_identification_number",
        ),
        ("Kanssahakija etunimi", "secondary_profile.first_name"),
        ("Kanssahakija sukunimi", "secondary_profile.last_name"),
        ("Kanssahakija sähköposti", "secondary_profile.email"),
        ("Kanssahakija osoite", "secondary_profile.street_address"),
        ("Kanssahakija postinumero", "secondary_profile.postal_code"),
        ("Kanssahakija postitoimipaikka", "secondary_profile.city"),
        (
            "Kanssahakija henkilötunnus",
            "secondary_profile.national_identification_number",
        ),
        ("Lapsia", "has_children"),
        ("Kohteen osoite", "project_street_address"),
        ("Kohteen postinumero", "project_postal_code"),
        ("Kohteen postitoimipaikka", "project_city"),
        ("Huoneiston kokoonpano", "apartment_structure"),
        ("Asuinpinta-ala", "living_area"),
    ]

    ORDER_BY = ["apartment_uuid", "queue_position"]

    export_first_in_queue = "first_in_queue"

    allowed_apartment_export_types = [
        ApartmentReservationState.RESERVED.value,  # export all reservers
        ApartmentReservationState.SOLD.value,  # export all who have bought
        export_first_in_queue,  # export reservers who are first in queue
    ]

    def __init__(self, reservations: QuerySet, export_type: str):
        self.reservations: QuerySet = reservations
        self.export_type = export_type

    def filter_reservations(self):
        if self.export_type not in self.allowed_apartment_export_types:
            raise ValueError(f"Invalid export type '{self.export_type}'")

        reservations = self.reservations.exclude(
            state=ApartmentReservationState.CANCELED
        )

        if self.export_type == self.export_first_in_queue:
            reservations = reservations.filter(queue_position=1)
        elif self.export_type == ApartmentReservationState.SOLD.value:
            reservations = reservations.filter(state=ApartmentReservationState.SOLD)

        reservations = reservations.order_by(*self.ORDER_BY)

        self.reservations = reservations
        return reservations

    def get_rows(self):
        self.filter_reservations()
        rows = [self._get_header_row()]

        for reservation in self.reservations:
            apartment = get_apartment(
                reservation.apartment_uuid, include_project_fields=True
            )
            row = self.get_row(reservation, apartment)
            rows.append(row)
        
        # need to group reservations by apartment_number attribute
        sorted_content_rows = sorted(
            rows[1:], 
            key=lambda x: f"{x[0]}{x[1]}"
        ) 

        # don't sort header row, attach it later
        rows = [ rows[0] ] + sorted_content_rows

        return rows

    def get_row(self, reservation, apartment):
        line = []

        for column in self.COLUMNS:
            cell_value = _get_reservation_cell_value(column[1], apartment, reservation)
            line.append(cell_value)
        return line


class ApplicantExportService(CSVExportService):
    COLUMNS = [
        ("Primary applicant", "primary_profile.full_name"),
        ("Primary applicant address", "primary_profile.street_address"),
        ("Primary applicant e-mail", "primary_profile.email"),
        ("Secondary applicant", "secondary_profile.full_name"),
        ("Secondary applicant address", "secondary_profile.street_address"),
        ("Secondary applicant e-mail", "secondary_profile.email"),
        ("Queue position", "queue_position"),
        ("Has children", "has_children"),
        ("Project address", "project_street_address"),
        ("Apartment number", "apartment_number"),
        ("Apartment structure", "apartment_structure"),
        ("Apartment area", "living_area"),
    ]

    def __init__(self, reservations):
        self.reservations = reservations

    def get_reservations(self):
        return self.reservations

    def get_rows(self):
        rows = [self._get_header_row()]
        for reservation in self.reservations:
            apartment = get_apartment(
                reservation.apartment_uuid, include_project_fields=True
            )
            row = self.get_row(reservation, apartment)
            rows.append(row)
        return rows

    def get_row(self, reservation, apartment):
        line = []
        for column in self.COLUMNS:
            cell_value = _get_reservation_cell_value(column[1], apartment, reservation)
            line.append(cell_value)
        return line


class ProjectLotteryResultExportService(CSVExportService):
    CSV_TITLE = "ARVONTATULOKSET"

    def __init__(self, project):
        self.project = project
        if project.project_ownership_type.lower() == "haso":
            self.COLUMNS = [
                ("Apartment number", "apartment_number"),
                ("Apartment structure", "apartment_structure"),
                ("Apartment area", "living_area"),
                ("Position", "lottery_position"),
                ("Right of residence", "right_of_residence"),
                ("Primary applicant", "primary_profile.full_name"),
                ("Secondary applicant", "secondary_profile.full_name"),
            ]
        else:
            self.COLUMNS = [
                ("Apartment number", "apartment_number"),
                ("Apartment structure", "apartment_structure"),
                ("Apartment area", "living_area"),
                ("Position", "lottery_position"),
                ("Primary applicant", "primary_profile.full_name"),
                ("Secondary applicant", "secondary_profile.full_name"),
                ("Has children", "has_children"),
            ]

    def get_reservations_by_apartment_uuid(self, apartment_uuid):
        return (
            ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)
            .exclude(application_apartment__lotteryeventresult__isnull=True)
            .order_by("application_apartment__lotteryeventresult__result_position")
        )

    def _get_document_title(self, apartment_uuids):
        lottery_completed_at = LotteryEvent.objects.filter(
            apartment_uuid__in=apartment_uuids
        ).aggregate(Max("timestamp"))["timestamp__max"]
        return [
            [
                self.CSV_TITLE,
                "Arvonta suoritettu",
                lottery_completed_at.strftime("%d.%m.%Y kello %H:%M"),
            ],
            [""],
            [self.project.project_housing_company],
        ]

    def get_rows(self):
        apartment_uuids = get_apartment_uuids(self.project.project_uuid)
        rows = [*self._get_document_title(apartment_uuids), self._get_header_row()]

        # collect rows first to this dict grouped by apartment number so that they can
        # be sorted by apartment number for the final result
        apartment_dict = {}

        for apartment_uuid in apartment_uuids:
            reservations = self.get_reservations_by_apartment_uuid(apartment_uuid)
            apartment = get_apartment(apartment_uuid, include_project_fields=True)
            apartment_dict[apartment.apartment_number] = [
                self.get_row(apartment=apartment if idx == 0 else None, reservation=r)
                for idx, r in enumerate(reservations)
            ] or [
                # no reservations, just apartment fields
                self.get_row(apartment)
            ]

        for apartment_rows in dict(
            sorted(
                apartment_dict.items(),
                key=lambda item: get_apartment_number_sort_tuple(item[0]),
            )
        ).values():
            rows.extend(apartment_rows)

        return rows

    def get_row(self, apartment=None, reservation=None):
        line = []
        for column in self.COLUMNS:
            cell_value = _get_reservation_cell_value(column[1], apartment, reservation)
            line.append(cell_value)
        return line


class SaleReportExportService(CSVExportService):
    COLUMNS = [
        ("Project address", "project_street_address"),
        ("Sold HITAS apartments", "hitas_sold_apartment_count"),
        ("Sold HASO apartments", "haso_sold_apartment_count"),
        ("Unsold apartments", "unsold_apartment_count"),
    ]

    def __init__(self, sold_events):
        self.sold_events = sold_events
        self.project_uuids = self._get_project_uuids()

    def get_rows(self):
        rows = [self._get_header_row()]
        total_hitas_sold = total_haso_sold = total_unsold = 0
        for project_uuid in self.project_uuids:
            project = get_project(project_uuid)
            row = self.get_row(project)
            rows.append(row)
            total_hitas_sold += int(row[1] or 0)
            total_haso_sold += int(row[2] or 0)
            total_unsold += int(row[3])
        # Add a total row at the bottom
        total_row = ["Total", total_hitas_sold, total_haso_sold, total_unsold]
        rows.append(total_row)
        return rows

    def get_row(self, project):
        line = []
        apartment_uuids = get_apartment_uuids(project.project_uuid)
        total_sold = len(
            [
                apartment_uuid
                for apartment_uuid in apartment_uuids
                if get_apartment_state_from_apartment_uuid(apartment_uuid)
                == ApartmentState.SOLD.value
            ]
        )
        reported_sold = len(
            [
                e
                for e in self.sold_events
                if str(e.reservation.apartment_uuid) in apartment_uuids
            ]
        )
        remaining = project.project_apartment_count - total_sold
        for column in self.COLUMNS:
            cell_value = ""
            if column[1].startswith(project.project_ownership_type.lower()):
                cell_value = reported_sold
            if column[1] == "project_street_address":
                cell_value = project.project_street_address
            if column[1] == "unsold_apartment_count":
                cell_value = remaining
            line.append(cell_value)
        return line

    def _get_project_uuids(self):
        project_uuids = set()
        for e in self.sold_events:
            project_uuid = get_apartment_project_uuid(
                e.reservation.apartment_uuid
            ).project_uuid
            project_uuids.add(project_uuid)
        return project_uuids
