import csv
import operator
from abc import abstractmethod
from io import StringIO

from apartment.elastic.queries import get_apartment, get_apartment_uuids
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation


def _get_reservation_cell_value(column_name, apartment, reservation, application=None):
    cell_value = ""
    # Profile fields
    if column_name.startswith("primary") or column_name.startswith("secondary"):
        if (
            column_name.startswith("secondary")
            and reservation.customer.secondary_profile is None
        ):
            cell_value = None
        else:
            cell_value = operator.attrgetter(column_name)(reservation.customer)
    if column_name == "has_children":
        cell_value = bool(reservation.customer.has_children)
    if column_name == "queue_position":
        cell_value = reservation.queue_position
    # Apartment fields
    if column_name in [
        "project_street_address",
        "apartment_number",
        "apartment_structure",
        "living_area",
        "floor",
    ]:
        cell_value = getattr(apartment, column_name)
    # Application fields
    if column_name == "right_of_residence" and application is not None:
        cell_value = application.right_of_residence
    return cell_value


class CSVExportService:
    CSV_DELIMITER = ";"
    FILE_ENCODING = "utf-8"
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
        first_length = len(lines[0])
        assert all([len(line) == first_length for line in lines])

        io = StringIO()
        csv_writer = csv.writer(
            io, delimiter=self.CSV_DELIMITER, quoting=csv.QUOTE_NONNUMERIC
        )
        for line in lines:
            csv_writer.writerow(line)

        return io.getvalue()


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
    COLUMNS = [
        ("Project address", "project_street_address"),
        ("Apartment number", "apartment_number"),
        ("Apartment structure", "apartment_structure"),
        ("Apartment area", "living_area"),
        ("Apartment floor", "floor"),
        ("Queue position", "queue_position"),
        ("Right of residence", "right_of_residence"),
        ("Primary applicant", "primary_profile.full_name"),
        ("Primary applicant address", "primary_profile.street_address"),
        ("Primary applicant e-mail", "primary_profile.email"),
        ("Secondary applicant", "secondary_profile.full_name"),
        ("Secondary applicant address", "secondary_profile.street_address"),
        ("Secondary applicant e-mail", "secondary_profile.email"),
        ("Has children", "has_children"),
    ]

    def __init__(self, project):
        self.project = project

    def get_reservations_by_apartment_uuid(self, apartment_uuid):
        return (
            ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)
            .exclude(state=ApartmentReservationState.CANCELED)
            .order_by("queue_position")
        )

    def get_rows(self):
        rows = [self._get_header_row()]
        apartment_uuids = get_apartment_uuids(self.project.project_uuid)
        for apartment_uuid in apartment_uuids:
            reservations = self.get_reservations_by_apartment_uuid(apartment_uuid)
            apartment = get_apartment(apartment_uuid, include_project_fields=True)
            for reservation in reservations:
                row = self.get_row(reservation, apartment)
                rows.append(row)
        return rows

    def get_row(self, reservation, apartment):
        line = []
        application = None
        if reservation.application_apartment is not None:
            application = reservation.application_apartment.application
        for column in self.COLUMNS:
            cell_value = _get_reservation_cell_value(
                column[1], apartment, reservation, application=application
            )
            line.append(cell_value)
        return line
