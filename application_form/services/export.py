import csv
from io import StringIO

from apartment.elastic.queries import get_apartment


class ApplicantExportService:
    CSV_DELIMITER = ";"
    FILE_ENCODING = "utf-8"
    COLUMNS = [
        ("Full name", "full_name"),
        ("Email address", "email"),
        ("Lottery result", "queue_position"),
        ("Has children", "has_children"),
        ("Project address", "project_street_address"),
        ("Apartment number", "apartment_number"),
        ("Apartment structure", "apartment_structure"),
        ("Apartment area", "living_area"),
    ]

    def _get_header_row(self):
        return [col[0] for col in self.COLUMNS]

    def __init__(self, reservations):
        self.reservations = reservations

    def get_reservations(self):
        return self.reservations

    def write_csv_file(self, path):
        csv_string = self.get_csv_string()
        with open(path, encoding=self.FILE_ENCODING, mode="w") as f:
            f.write(csv_string)

    def get_csv_string(self):
        return self._make_csv(self.get_rows())

    def get_rows(self):
        rows = [self._get_header_row()]

        for reservation in self.reservations:
            apartment = get_apartment(
                reservation.apartment_uuid, include_project_fields=True
            )
            row = self.get_row(
                reservation.customer.primary_profile, reservation, apartment
            )
            rows.append(row)
            # Some reservation there are co-applicants
            if reservation.customer.secondary_profile:
                row = self.get_row(
                    reservation.customer.secondary_profile, reservation, apartment
                )
                rows.append(row)
        return rows

    def get_row(self, profile, reservation, apartment):
        line = []
        for column in self.COLUMNS:
            cell_value = ""
            # Profile fields
            if column[1] in ["full_name", "email"]:
                cell_value = getattr(profile, column[1])
            if column[1] == "has_children":
                cell_value = bool(reservation.customer.has_children)
            if column[1] == "queue_position":
                cell_value = reservation.queue_position
            # Apartment fields
            if column[1] in [
                "project_street_address",
                "apartment_number",
                "apartment_structure",
                "living_area",
            ]:
                cell_value = getattr(apartment, column[1])
            line.append(cell_value)
        return line

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
