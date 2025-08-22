import csv
import logging
import operator
import re
from abc import abstractmethod
from datetime import datetime
from decimal import Decimal
from io import BytesIO, StringIO
from typing import List, Union

import xlsxwriter
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import CharField, Max, QuerySet
from django.db.models.functions import Cast

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import (
    get_apartment,
    get_apartment_project_uuid,
    get_apartment_uuids,
    get_apartments,
    get_project,
)
from apartment.enums import ApartmentState, OwnershipType
from apartment.utils import get_apartment_state_from_apartment_uuid
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation, LotteryEvent
from application_form.models.reservation import ApartmentReservationStateChangeEvent
from application_form.services.types import SalesReportProjectTotalsDict
from application_form.utils import get_apartment_number_sort_tuple
from invoicing.enums import InstallmentType, PaymentStatus
from invoicing.models import ApartmentInstallment

_logger = logging.getLogger(__name__)


def _get_reservation_cell_value(
    column_name: str,
    apartment: ApartmentDocument = None,
    reservation: Union[ApartmentReservation, None] = None,
):
    if not reservation:
        return ""

    roo_column_names = [
        InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT.value,
        InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_2.value,
        InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3.value,
        "Maksettu",
    ]
    if column_name in roo_column_names:
        return None

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
        return getattr(apartment, column_name) or ""
    # Profile fields
    if column_name.startswith("primary") or column_name.startswith("secondary"):
        if (
            column_name.startswith("secondary")
            and reservation.customer.secondary_profile is None
        ):
            return ""
        else:
            return operator.attrgetter(column_name)(reservation.customer) or ""
    if column_name == "has_children":
        return "X" if bool(reservation.has_children) else ""
    if column_name == "has_hitas_ownership":
        if reservation.has_hitas_ownership is None:
            return ""
        return "Kyllä" if bool(reservation.has_hitas_ownership) else "Ei"
    if column_name == "lottery_position":
        return reservation.application_apartment.lotteryeventresult.result_position
    if column_name == "queue_position":
        return reservation.queue_position
    if column_name == "right_of_residence":
        return reservation.right_of_residence
    return ""


class XlsxExportService:
    COL_WIDTH = 4

    @abstractmethod
    def get_rows(self):
        pass

    def write_xlsx_file(self) -> BytesIO:
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        self._make_xlsx(workbook)
        workbook.close()
        output.seek(0)
        return output

    def _make_xlsx(
        self, workbook: xlsxwriter.workbook.Workbook
    ) -> xlsxwriter.workbook.Workbook:
        worksheet = workbook.add_worksheet()

        rows = self.get_rows()
        last_column_idx = max(len(r) for r in rows)

        cell_format_default = workbook.add_format()

        for i, row in enumerate(rows):
            # if the last item in the row is a hex representation of a color
            # use it as the row's background. Not the smartest way to do this
            if str(row[-1]).startswith("#"):
                cell_format = workbook.add_format({"bg_color": row.pop()})

            for j, cell in enumerate(row):
                worksheet.write(i, j, cell, cell_format)

            if cell_format.bg_color is not False:
                # color rows to the same width regardless of content
                for k in range(j, last_column_idx):
                    try:
                        cell = rows[i][k]
                    except IndexError:
                        cell = ""
                    worksheet.write(i, k, cell, cell_format)

            cell_format = cell_format_default

        worksheet.set_column(0, last_column_idx, self.COL_WIDTH)


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
        ("Hitas omistus", "has_hitas_ownership"),
        ("Kohteen osoite", "project_street_address"),
        ("Kohteen postinumero", "project_postal_code"),
        ("Kohteen postitoimipaikka", "project_city"),
        ("Huoneiston kokoonpano", "apartment_structure"),
        ("Asuinpinta-ala", "living_area"),
    ]

    COLUMNS_ROO_PAYMENTS = [
        ("AO-maksu 1", InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT.value),
        ("Maksettu", "Maksettu"),
        ("AO-maksu 2", InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_2.value),
        ("Maksettu", "Maksettu"),
        ("AO-maksu 3", InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3.value),
        ("Maksettu", "Maksettu"),
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

        self.add_roo_columns = (
            self.any_reservation_has_roo_installments()
            and export_type == ApartmentReservationState.SOLD.value
        )

        if self.add_roo_columns:
            self.COLUMNS = self.COLUMNS + self.COLUMNS_ROO_PAYMENTS

    def _get_header_row(self):
        return [col[0] for col in self.COLUMNS]

    def any_reservation_has_roo_installments(self) -> bool:
        """
        Returns True if any reservation in the set has Right Of Occupancy installments
        associated with it.
        """
        return self._get_apartment_roo_installments().exists()

    def _get_apartment_roo_installments(self) -> QuerySet[ApartmentReservation]:
        """
        Gets Right Of Occupancy installments for the reservations
        """
        return ApartmentInstallment.objects.filter(
            apartment_reservation__in=self.reservations,
            type__in=[
                InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT,
                InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_2,
                InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3,
            ],
        )

    def get_order_key(self, row):
        # turn letter-number combo into numeric values for comparison
        # this is because sorting A1, A2, A13 alphabetically returns A1, A13, A2
        convert = lambda text: int(text) if text.isdigit() else text  # noqa: E731
        return [convert(c) for c in re.split(r"(\d+)", row[0])]

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
        sorted_content_rows = sorted(rows[1:], key=self.get_order_key)

        # don't sort header row, attach it later
        rows = [rows[0]] + sorted_content_rows

        return rows

    def get_row(self, reservation: ApartmentReservation, apartment: ApartmentDocument):
        line = []
        columns = self.COLUMNS
        export_type_is_sold = self.export_type == ApartmentReservationState.SOLD.value
        is_haso = apartment.project_ownership_type == OwnershipType.HASO.value

        if export_type_is_sold and is_haso:
            columns = columns + self.COLUMNS_ROO_PAYMENTS

        for column in columns:
            cell_value = _get_reservation_cell_value(column[1], apartment, reservation)
            if cell_value is not None:
                line.append(cell_value)

        if export_type_is_sold and is_haso:
            for installment in self.get_right_of_occupancy_installments(reservation):
                line += [
                    installment.value,
                    (
                        "X"
                        if installment.payment_status.value == PaymentStatus.PAID.value
                        else ""
                    ),
                ]
                pass

        return line

    def get_right_of_occupancy_installments(
        self, reservation: ApartmentReservation
    ) -> QuerySet[ApartmentInstallment]:
        installments: QuerySet[ApartmentInstallment] = (
            self._get_apartment_roo_installments()
            .filter(apartment_reservation=reservation)
            .order_by("type")
        )
        return installments


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


class XlsxSalesReportExportService(XlsxExportService):
    COL_WIDTH = 26
    HIGHLIGHT_COLOR = "#E8E8E8"

    def __init__(self, sold_events, project_uuids):
        self.sold_events = sold_events
        self.project_uuids = project_uuids

        # cast uuidfield to charfield for comparison
        self.sold_apartment_uuids = (
            sold_events.annotate(
                auuid=Cast("reservation__apartment_uuid", output_field=CharField())
            )
            .order_by()
            .distinct()
            .values_list("auuid", flat=True)
        )

        self.projects = self._get_projects()
        _logger.debug(
            "Creating XlsxSalesReport with projects %s and sold_apartment_uuids %s",
            self.projects,
            self.sold_apartment_uuids,
        )

    def _get_project_totals(
        self, project: ApartmentDocument
    ) -> SalesReportProjectTotalsDict:
        """Groups total sold HITAS, sold HASO apartments, counts unsold apartments
        and the total sales sums for a project.

        Args:
            project (ApartmentDocument): _description_

        Returns:
            dict: ```
            {
                "sold_haso_apartments_count": int
                "sold_hitas_apartments_count": int
                "unsold_apartments_count": int
                "haso_right_of_occupancy_payment_sum": Decimal
                "hitas_sales_price_sum": Decimal
                "hitas_debt_free_sales_price_sum": Decimal
            }
            ```
        """
        project_apartments = get_apartments(
            project.project_uuid, include_project_fields=True
        )
        sold_apartments = self._get_sold_apartments(project_apartments)
        sold_hitas_apartments = self._get_hitas_apartments(sold_apartments)
        sold_haso_apartments = self._get_haso_apartments(sold_apartments)

        haso_right_of_occupancy_payment_sum = self._sum_cents(
            x.right_of_occupancy_payment or 0 for x in sold_haso_apartments
        )
        hitas_sales_price_sum = self._sum_cents(
            x.sales_price or 0 for x in sold_hitas_apartments
        )
        hitas_debt_free_sales_price_sum = self._sum_cents(
            x.debt_free_sales_price or 0 for x in sold_hitas_apartments
        )

        unsold_apartments_count = self._get_unsold_count(project_apartments)

        return {
            "sold_haso_apartments_count": len(sold_haso_apartments),
            "sold_hitas_apartments_count": len(sold_hitas_apartments),
            "unsold_apartments_count": unsold_apartments_count,
            "haso_right_of_occupancy_payment_sum": haso_right_of_occupancy_payment_sum,
            "hitas_sales_price_sum": hitas_sales_price_sum,
            "hitas_debt_free_sales_price_sum": hitas_debt_free_sales_price_sum,
        }

    def get_rows(self):
        apartments = []
        rows = []

        project_rows = []
        first = True

        for project in self.projects:

            project_apartments = get_apartments(
                project.project_uuid, include_project_fields=True
            )

            apartments += project_apartments
            rows_for_project = self._get_project_rows(
                project, project_apartments, first=first
            )

            # ensure the sub-header for projects is outputted even if the first
            # project doesn't have any rows to output
            if len(rows_for_project) > 0:
                first = False

            project_rows += rows_for_project

        hitas_sold = self._get_sold_hitas_apartments(apartments)
        haso_sold = self._get_sold_haso_apartments(apartments)

        header_rows = [
            [
                "Kohteen osoite",
                "Asuntoja yhteensä",
                "Myydyt HITAS-asunnot",
                "Myydyt HASO-asunnot",
                "Myymättömät asunnot",
                self.HIGHLIGHT_COLOR,
            ],
        ]

        sum_rows = [
            [""],
            [""],
            self._get_total_sold_row(apartments),
            [
                "Kauppahinnat yhteensä",
                self._sum_cents(x.sales_price or 0 for x in hitas_sold),
                self._sum_cents(x.debt_free_sales_price or 0 for x in hitas_sold),
                self._sum_cents(x.right_of_occupancy_payment or 0 for x in haso_sold),
                self.HIGHLIGHT_COLOR,
            ],
        ]

        rows += header_rows
        rows += project_rows
        rows += sum_rows
        return rows

    def _get_project_rows(
        self,
        project: ApartmentDocument,
        apartments: List[ApartmentDocument],
        first,
    ) -> List[List]:
        """Generates the per-project rows.

        Args:
            project (ApartmentDocument): Project
            apartments (List[ApartmentDocument]): List of apartments for the project.
            Passed as an argument to reduce calls to `get_apartments()`
            first (bool): if `True`, adds a header row before the other rows
        """
        _logger.debug("Project %s", project.project_uuid)

        sold_apartments = self._get_sold_apartments(apartments)
        is_haso = self._is_haso(project)
        is_hitas = self._is_hitas(project)
        totals = self._get_project_totals(project)

        rows = []

        rows.append(
            [
                project.project_street_address,
                len(apartments),
                totals["sold_hitas_apartments_count"],
                totals["sold_haso_apartments_count"],
                totals["unsold_apartments_count"],
            ]
        )

        if first:
            rows.append(
                [
                    "Huoneisto",
                    "Myyntihinta",
                    "Velaton hinta",
                    "Luovutushinta",
                    "Kaupantekopäivä",
                    self.HIGHLIGHT_COLOR,
                ]
            )

        for apartment in sold_apartments:
            rows.append(self._get_apartment_row(apartment))

        totals_row = [
            "Yhteensä",
            (
                self._sum_cents(x.sales_price or 0 for x in sold_apartments)
                if is_hitas
                else ""
            ),  # noqa: E501
            (
                self._sum_cents(x.debt_free_sales_price or 0 for x in sold_apartments)
                if is_hitas
                else ""
            ),  # noqa: E501
            (
                self._sum_cents(
                    x.right_of_occupancy_payment or 0 for x in sold_apartments
                )
                if is_haso
                else ""
            ),  # noqa: E501
            self.HIGHLIGHT_COLOR,
        ]
        rows.append(totals_row)
        rows.append([""])

        return rows

    def _get_total_sold_row(
        self,
        apartments: List[ApartmentDocument],
    ) -> List[Union[str, Decimal]]:

        hitas_sold_count = len(self._get_sold_hitas_apartments(apartments))
        haso_sold_count = len(self._get_sold_haso_apartments(apartments))

        return [
            "Kaupat lukumäärä yhteensä",
            "",
            hitas_sold_count,
            haso_sold_count,
            self._get_unsold_count(apartments),
            self.HIGHLIGHT_COLOR,
        ]

    def _get_apartment_row(self, apartment: ApartmentDocument) -> List:
        is_haso = self._is_haso(apartment)
        is_hitas = self._is_hitas(apartment)

        row = [
            apartment.apartment_number,
            self._cents_to_eur(apartment.sales_price) if is_hitas else "",
            self._cents_to_eur(apartment.debt_free_sales_price) if is_hitas else "",
            self._cents_to_eur(apartment.right_of_occupancy_payment) if is_haso else "",
            self._get_apartment_date_of_sale(apartment),
        ]

        return row

    def _get_unsold_count(self, apartments: List[ApartmentDocument]) -> int:
        """Counts unsold apartments based on the apartment's state, disregarding
        any 'sold'-events the apartment may have.

        Args:
            apartments (List[ApartmentDocument]): Unfiltered list of apartments
        """
        sold_apartments = self._get_sold_apartments_based_on_state(apartments)

        unsold_count = len(apartments) - len(sold_apartments)
        return unsold_count

    def _get_sold_apartments(
        self, apartments: List[ApartmentDocument]
    ) -> List[ApartmentDocument]:
        """Gets sold apartments based on their state and
        whether or not the `ApartmentReservationStateChangeEvent` with
        their apartment uuid and the state 'sold' was passed to the export service.

        Args:
            apartments (List[ApartmentDocument]): unfiltered ApartmentDocument list
        Returns:
            List[ApartmentDocument]: filtered ApartmentDocument list
        """

        return [
            apartment
            for apartment in self._get_sold_apartments_based_on_state(apartments)
            if apartment.uuid in self.sold_apartment_uuids
        ]

    def _get_sold_apartments_based_on_state(
        self, apartments: List[ApartmentDocument]
    ) -> List[ApartmentDocument]:
        """Gets sold apartments based on their state.

        Args:
            apartments (List[ApartmentDocument]): unfiltered ApartmentDocument list
        Returns:
            List[ApartmentDocument]: filtered ApartmentDocument list
        """
        return [
            apartment
            for apartment in apartments
            if (
                get_apartment_state_from_apartment_uuid(apartment.uuid)
                == ApartmentState.SOLD.value
            )
        ]

    def _get_sold_hitas_apartments(
        self, apartments: List[ApartmentDocument]
    ) -> List[ApartmentDocument]:
        """Gets sold hitas-apartments from a list of unfiltered apartments based on the
        state and 'sold'-events

        Args:
            apartments (List[ApartmentDocument]): unfiltered list of apartments

        Returns:
            List[ApartmentDocument]: filtered list of apartments
        """
        sold_apartments = self._get_sold_apartments(apartments)
        sold_hitas_apartments = self._get_hitas_apartments(sold_apartments)
        return sold_hitas_apartments

    def _get_sold_haso_apartments(
        self, apartments: List[ApartmentDocument]
    ) -> List[ApartmentDocument]:
        """Gets sold haso-apartments from a list of unfiltered apartments based on the
        state and 'sold'-events

        Args:
            apartments (List[ApartmentDocument]): unfiltered list of apartments

        Returns:
            List[ApartmentDocument]: filtered list of apartments
        """
        sold_apartments = self._get_sold_apartments(apartments)
        sold_haso_apartments = self._get_haso_apartments(sold_apartments)
        return sold_haso_apartments

    def _get_hitas_apartments(self, apartments: List[ApartmentDocument]):
        return [apartment for apartment in apartments if self._is_hitas(apartment)]

    def _get_haso_apartments(self, apartments: List[ApartmentDocument]):
        return [apartment for apartment in apartments if self._is_haso(apartment)]

    def _get_apartment_sold_event(
        self, apartment: ApartmentDocument
    ) -> Union[ApartmentReservationStateChangeEvent, None]:
        return (
            self.sold_events.filter(
                reservation__apartment_uuid=apartment.uuid,
                state=ApartmentReservationState.SOLD,
            )
            .order_by("-id")
            .first()
        )

    def _get_apartment_date_of_sale(
        self, apartment: ApartmentDocument
    ) -> Union[datetime, None]:
        """Get the date of sale for the apartment.
        TODO: optimize!!

        Args:
            apartment (ApartmentDocument):
        """
        state_change_event = self._get_apartment_sold_event(apartment)
        if not state_change_event:
            return None
        return state_change_event.timestamp.strftime("%d.%m.%Y")

    def _is_haso(self, project: ApartmentDocument):
        if not project.project_ownership_type:
            return False

        return project.project_ownership_type.lower() == OwnershipType.HASO.value

    def _is_hitas(self, project: ApartmentDocument):
        if not project.project_ownership_type:
            return False

        return project.project_ownership_type.lower() == OwnershipType.HITAS.value

    def _get_projects(self):
        projects = []
        uuids = []
        for project_uuid in self.project_uuids:
            try:
                if project_uuid not in uuids:
                    projects.append(get_project(project_uuid))
                    uuids.append(project_uuid)
            except ObjectDoesNotExist:
                _logger.error(
                    "Project %s does not exist in ElasticSearch",
                    project_uuid,
                )

        return sorted(projects, key=lambda x: x.project_street_address)

    def _sum_cents(self, cents: List[int]):
        return sum(self._cents_to_eur(cent) for cent in cents)

    def _cents_to_eur(self, cents: int) -> Decimal:
        if cents is None:
            cents = Decimal(0.00)
        return Decimal(cents) / 100


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
