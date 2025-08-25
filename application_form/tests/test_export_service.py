import collections
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from typing import List, Union

import pytest
from _pytest.fixtures import fixture
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils import timezone

from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import (
    get_apartment,
    get_apartment_uuids,
    get_apartments,
    get_project,
)
from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from apartment.utils import get_apartment_state_from_apartment_uuid
from application_form.enums import ApartmentReservationState
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
)
from application_form.services.application import cancel_reservation
from application_form.services.export import (
    ApplicantExportService,
    ApplicantMailingListExportService,
    ProjectLotteryResultExportService,
    SaleReportExportService,
    XlsxSalesReportExportService,
)
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.conftest import sell_apartments
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApartmentReservationStateChangeEventFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from customer.tests.factories import CustomerFactory
from invoicing.enums import InstallmentType, PaymentStatus
from invoicing.models import ApartmentInstallment
from invoicing.tests.factories import ApartmentInstallmentFactory, PaymentFactory
from users.tests.factories import ProfileFactory


@fixture
def applicant_export_service(elastic_project_with_5_apartments):
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile, secondary_profile=None)
    application = ApplicationFactory(customer=customer)
    reservations = []
    for i, apartment in enumerate(apartments):
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid,
            application=application,
            priority_number=i + 1,
        )
        reservations.append(
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid,
                application_apartment=application_apartment,
                customer=customer,
            )
        )

    return ApplicantExportService(reservations)


@fixture
def applicant_export_service_with_additional_applicant(
    elastic_project_with_5_apartments,
):
    project_uuid, apartments = elastic_project_with_5_apartments
    profile = ProfileFactory()
    secondary_profile = ProfileFactory()
    customer = CustomerFactory(
        primary_profile=profile, secondary_profile=secondary_profile
    )
    application = ApplicationFactory(customer=customer)
    reservations = []

    for i, apartment in enumerate(apartments):
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid,
            application=application,
            priority_number=i + 1,
        )
        reservations.append(
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid,
                application_apartment=application_apartment,
                customer=customer,
            )
        )
    return ApplicantExportService(reservations)


@fixture
def reservations(elastic_project_with_24_apartments):
    project_uuid, apartments = elastic_project_with_24_apartments

    profile = ProfileFactory()
    profile_secondary = ProfileFactory()
    customer = CustomerFactory(
        primary_profile=profile, secondary_profile=profile_secondary
    )
    application = ApplicationFactory(customer=customer)
    reservations = []

    for i, apartment in enumerate(apartments):
        application_apartment = ApplicationApartmentFactory(
            apartment_uuid=apartment.uuid,
            application=application,
            priority_number=i + 1,
        )
        reservations.append(
            ApartmentReservationFactory(
                apartment_uuid=apartment.uuid,
                application_apartment=application_apartment,
                customer=customer,
                queue_position=i + 1,
            )
        )

    return reservations


def _validate_mailing_list_csv(
    csv_rows: List[List[str]],
    reservations: List[ApartmentReservation],
    export_service: Union[ApplicantMailingListExportService, None] = None,
):
    """Validates a mailing list CSV created by ApplicationMailingListExportService

    Args:
        csv_rows (List[List[str]]): content of the rows
        reservations (List[ApartmentReservation]): reservations used to generate the csv
        export_service (ApplicantMailingListExportService|None): Optional instance of
        the ApplicantMailingListExportService in case the instance's columns are changed
    """
    columns = ApplicantMailingListExportService.COLUMNS
    if export_service is not None:
        columns = export_service.COLUMNS

    for idx, header in enumerate(csv_rows[0]):
        assert header == columns[idx][0]

    content_rows = csv_rows[1:]

    reservations = sorted(
        reservations, key=lambda x: get_apartment(x.apartment_uuid).apartment_number
    )

    # placeholder for empty primary_profile or secondary_profile to simplify code below
    class empty_profile:
        first_name = None
        last_name = None
        email = None
        street_address = None
        postal_code = None
        city = None
        national_identification_number = None

    payment_status_labels = {
        PaymentStatus.PAID: "maksettu",
        PaymentStatus.UNPAID: "",
        PaymentStatus.OVERPAID: "ylisuoritus",
        PaymentStatus.UNDERPAID: "alisuoritus",
    }

    for i, row in enumerate(content_rows):

        reservation = reservations[i]
        roo_installments: QuerySet[ApartmentInstallment] = (
            reservation.apartment_installments.filter(
                type__in=[
                    InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT,
                    InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_2,
                    InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3,
                ]
            ).order_by("type")
        )

        apartment = get_apartment(
            reservation.apartment_uuid, include_project_fields=True
        )

        primary_profile = reservation.customer.primary_profile or empty_profile
        secondary_profile = reservation.customer.secondary_profile or empty_profile

        expected_row = [
            apartment.apartment_number or "",
            reservation.queue_position,
            primary_profile.first_name or "",
            primary_profile.last_name or "",
            primary_profile.email or "",
            primary_profile.street_address or "",
            primary_profile.postal_code or "",
            primary_profile.city or "",
            primary_profile.national_identification_number or "",
            secondary_profile.first_name or "",
            secondary_profile.last_name or "",
            secondary_profile.email or "",
            secondary_profile.street_address or "",
            secondary_profile.postal_code or "",
            secondary_profile.city or "",
            secondary_profile.national_identification_number or "",
            "X" if bool(reservation.has_children) else "",
            "Kyllä" if bool(reservation.has_hitas_ownership) else "Ei",
            apartment.project_street_address or "",
            apartment.project_postal_code or "",
            apartment.project_city or "",
            apartment.apartment_structure or "",
            apartment.living_area or "",
        ]

        if export_service is not None and export_service.add_roo_columns:
            for roo_installment in roo_installments:
                expected_row += [
                    roo_installment.value,
                    payment_status_labels[roo_installment.payment_status],
                ]

        for expected_field_value, value in zip(expected_row, row):
            assert expected_field_value == value

        assert row == expected_row


@pytest.mark.django_db
def test_sorting_function(reservations):
    """
    Assert that the rows get sorted naturally, e.g.
    ["A1", "A2", "A10"] and not ["A1", "A10", "A2"]
    https://blog.codinghorror.com/sorting-for-humans-natural-sort-order/
    """
    reservation_queryset = ApartmentReservation.objects.filter(
        apartment_uuid__in=[res.apartment_uuid for res in reservations]
    )
    applicant_mailing_list_export_service = ApplicantMailingListExportService(
        reservation_queryset,
        export_type=ApartmentReservationState.RESERVED.value,
    )

    _sorted = sorted(
        ["A1", "A2", "A3", "A10"],
        key=applicant_mailing_list_export_service.get_order_key,
    )

    assert _sorted == ["A1", "A2", "A3", "A10"]
    pass


@pytest.mark.django_db
@pytest.mark.parametrize(
    "export_type,project_ownership_type,expected_column_count",
    [
        (ApartmentReservationState.SOLD.value, OwnershipType.HASO, 28),
        (ApartmentReservationState.SOLD.value, OwnershipType.HITAS, 23),
        (ApartmentReservationState.RESERVED.value, OwnershipType.HASO, 23),
        (
            ApplicantMailingListExportService.export_first_in_queue,
            OwnershipType.HASO,
            23,
        ),
    ],
)
def test_export_applicants_mailing_list_haso_payments(
    export_type: str, project_ownership_type: OwnershipType, expected_column_count: int
):
    """
    Test that the applicants mailing list CSV gets the Right Of Occupancy Payment
    installment columns when the project is a HASO project and the export mode is "SOLD"
    """

    apartment = ApartmentDocumentFactory(
        project_ownership_type=project_ownership_type.value
    )

    apartment_2 = ApartmentDocumentFactory(
        project_ownership_type=project_ownership_type.value
    )

    # add apartment with some empty attributes
    # to test that empty attributes dont cause misalignment with content row and header
    apartment_missing_attribs = ApartmentDocumentFactory(
        living_area=None, project_ownership_type=project_ownership_type.value
    )
    apartments = [apartment, apartment_2, apartment_missing_attribs]

    # add reservations and installments if HASO test case
    roo_installment_types = []

    if project_ownership_type == OwnershipType.HASO:
        roo_installment_types = [
            InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT,
            InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_2,
            InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3,
        ]

    apartment_uuids = []

    for idx, apt in enumerate(apartments):
        res = ApartmentReservationFactory(
            apartment_uuid=apt.uuid,
            state=ApartmentReservationState.SOLD,
            customer=CustomerFactory(
                primary_profile=ProfileFactory(),
                secondary_profile=ProfileFactory() if idx == 0 else None,
            ),
        )

        for jdx, installment_type in enumerate(roo_installment_types):
            installment = ApartmentInstallmentFactory(
                apartment_reservation=res,
                type=installment_type,
            )

            installment_value = [0, 10, -10][jdx]

            # only add underpaid payment to last apartment
            if idx != (len(apartments) - 1) and jdx == 2:
                continue

            PaymentFactory(
                apartment_installment=installment,
                amount=installment.value + installment_value,
            )

        apartment_uuids.append(apt.uuid)

    reservation_queryset = ApartmentReservation.objects.filter(
        apartment_uuid__in=apartment_uuids
    )

    applicant_mailing_list_export_service = ApplicantMailingListExportService(
        reservation_queryset,
        export_type=export_type,
    )

    filtered_reservations = applicant_mailing_list_export_service.filter_reservations()

    csv_lines = applicant_mailing_list_export_service.get_rows()

    _validate_mailing_list_csv(
        csv_lines, filtered_reservations, applicant_mailing_list_export_service
    )

    assert len(csv_lines[0]) == expected_column_count

    pass


@pytest.mark.django_db
def test_export_applicants_mailing_list_all(reservations):
    """Assert that getting all applicants except for state = 'CANCELED' works"""

    # convert list to queryset
    reservation_queryset = ApartmentReservation.objects.filter(
        apartment_uuid__in=[res.apartment_uuid for res in reservations]
    )
    reservation_queryset.update(state=ApartmentReservationState.SUBMITTED)
    first_reservation = reservation_queryset.first()
    first_reservation.state = ApartmentReservationState.CANCELED
    first_reservation.save()

    applicant_mailing_list_export_service = ApplicantMailingListExportService(
        reservation_queryset,
        export_type=ApartmentReservationState.RESERVED.value,
    )

    filtered_reservations = applicant_mailing_list_export_service.filter_reservations()

    csv_lines = applicant_mailing_list_export_service.get_rows()
    _validate_mailing_list_csv(csv_lines, filtered_reservations)
    assert len(filtered_reservations) == 23
    assert len(csv_lines) == 24


@pytest.mark.django_db
def test_export_applicants_mailing_list_first_in_queue(reservations):
    """Assert that filtering for reservations that are first in queue works."""

    # convert list to queryset
    reservation_queryset = ApartmentReservation.objects.filter(
        apartment_uuid__in=[res.apartment_uuid for res in reservations]
    )

    reservation_queryset.update(queue_position=2)
    last_reservation = reservation_queryset.last()
    last_reservation.queue_position = 1
    last_reservation.save()

    applicant_mailing_list_export_service = ApplicantMailingListExportService(
        reservation_queryset,
        export_type=ApplicantMailingListExportService.export_first_in_queue,
    )

    filtered_reservations = applicant_mailing_list_export_service.filter_reservations()
    csv_lines = applicant_mailing_list_export_service.get_rows()
    assert len(filtered_reservations) == 1
    assert len(csv_lines) == 2

    _validate_mailing_list_csv(csv_lines, filtered_reservations)


@pytest.mark.django_db
def test_export_applicants_mailing_list_sold(reservations):
    """Assert that filtering for reservations that have the state 'SOLD' works"""

    # convert list to queryset
    reservation_queryset = ApartmentReservation.objects.filter(
        apartment_uuid__in=[res.apartment_uuid for res in reservations]
    )
    reservation_queryset.update(state=ApartmentReservationState.SUBMITTED)
    first_reservation = reservation_queryset.first()
    first_reservation.state = ApartmentReservationState.SOLD
    first_reservation.save()

    applicant_mailing_list_export_service = ApplicantMailingListExportService(
        reservation_queryset,
        export_type=ApartmentReservationState.SOLD.value,
    )

    csv_lines = applicant_mailing_list_export_service.get_rows()
    filtered_reservations = applicant_mailing_list_export_service.filter_reservations()
    assert len(filtered_reservations) == 1
    assert len(csv_lines) == 2
    _validate_mailing_list_csv(csv_lines, filtered_reservations)


@pytest.mark.django_db
def test_export_applicants(applicant_export_service):
    csv_lines = applicant_export_service.get_rows()
    assert len(applicant_export_service.get_reservations()) == 5
    assert len(csv_lines) == 6
    for idx, header in enumerate(csv_lines[0]):
        assert header == ApplicantExportService.COLUMNS[idx][0]
    assert (
        csv_lines[1][0]
        == applicant_export_service.get_reservations()[
            0
        ].customer.primary_profile.full_name
    )

    assert csv_lines[1][3] == ""
    assert (
        csv_lines[2][0]
        == applicant_export_service.get_reservations()[
            1
        ].customer.primary_profile.full_name
    )
    assert csv_lines[2][3] == ""


@pytest.mark.django_db
def test_export_applicants_and_secondary_applicants(
    applicant_export_service_with_additional_applicant,
):
    export_service = applicant_export_service_with_additional_applicant
    csv_lines = export_service.get_rows()
    assert len(export_service.get_reservations()) == 5
    assert len(csv_lines) == 6
    for idx, header in enumerate(csv_lines[0]):
        assert header == ApplicantExportService.COLUMNS[idx][0]
    assert (
        csv_lines[1][0]
        == export_service.get_reservations()[0].customer.primary_profile.full_name
    )
    assert (
        csv_lines[1][3]
        == export_service.get_reservations()[0].customer.secondary_profile.full_name
    )


@pytest.mark.django_db
@pytest.mark.parametrize("ownership_type", ["HITAS", "HASO"])
def test_export_project_lottery_result(
    ownership_type,
    elastic_hitas_project_with_5_apartments,
    elastic_haso_project_with_5_apartments,
):
    if ownership_type == "HITAS":
        project_uuid, _ = elastic_hitas_project_with_5_apartments
    else:
        project_uuid, _ = elastic_haso_project_with_5_apartments

    apartment_uuids = get_apartment_uuids(project_uuid)
    for apartment_uuid in apartment_uuids:
        apt_app = ApplicationApartmentFactory.create_batch(
            2, apartment_uuid=apartment_uuid
        )
        add_application_to_queues(apt_app[0].application)
        add_application_to_queues(apt_app[1].application)
    distribute_apartments(project_uuid)
    # reservations added after the lottery shouldn't be included
    ApartmentReservationFactory(apartment_uuid=apartment_uuids[0], list_position=777)

    project = get_project(project_uuid)
    export_service = ProjectLotteryResultExportService(project)
    csv_lines = export_service.get_rows()
    csv_headers = csv_lines[3]
    csv_content = csv_lines[4:]
    assert len(csv_lines) == 14
    for idx, header in enumerate(csv_headers):
        assert header == export_service.COLUMNS[idx][0]

    first_reservation = export_service.get_reservations_by_apartment_uuid(
        apartment_uuids[0]
    ).first()
    last_reservation = export_service.get_reservations_by_apartment_uuid(
        apartment_uuids[-1]
    ).last()

    primary_applicant_column = 4 if ownership_type == "HITAS" else 5
    assert next(
        (
            line
            for line in csv_content
            if line[primary_applicant_column]
            == first_reservation.customer.primary_profile.full_name
        ),
        None,
    )
    assert next(
        (
            line
            for line in csv_content
            if line[primary_applicant_column]
            == last_reservation.customer.primary_profile.full_name
        ),
        None,
    )


def get_sold_state_events(
    start=timezone.now() - timedelta(days=7), end=timezone.now() + timedelta(days=7)
) -> Union[QuerySet, List[ApartmentReservationStateChangeEvent]]:
    """Fetches all ApartmentReservationStateChangeEvent objects within the given
    date range

    Args:
        start (Datetime): Find state change events from this date onwards.
        end (Datetime): Find state change events that are at the latest from this date

    Returns:
        Union[QuerySet, List[ApartmentReservationStateChangeEvent]]
    """
    return ApartmentReservationStateChangeEvent.objects.filter(
        state=ApartmentReservationState.SOLD, timestamp__date__range=[start, end]
    )
    pass


@pytest.mark.django_db
def test_sale_report_invalid_money_amount():
    """test that invalid money amounts are handled right"""

    # QuerySet contents are irrelevant, just need to init the ExportService
    sold_events = ApartmentReservationStateChangeEvent.objects.all()
    cent_sum = XlsxSalesReportExportService(sold_events, [])._sum_cents(
        [100, 100, None, 100]
    )
    assert cent_sum == Decimal(3)


@pytest.mark.django_db
def test_export_project_with_no_sales_shows_on_report():
    """Projects with no sales should be still shown on report when selected"""
    sold_apartments_project = ApartmentDocumentFactory(project_ownership_type="Hitas")
    apartments = [sold_apartments_project]

    sell_count = 2

    for _ in range(4):
        apartment = ApartmentDocumentFactory(
            project_ownership_type="Hitas",
            project_uuid=sold_apartments_project.project_uuid,
        )
        apartments.append(apartment)

    sell_apartments(sold_apartments_project.project_uuid, sell_count)

    # create apartment on a new project
    unsold_apartments_project = ApartmentDocumentFactory(project_ownership_type="Hitas")
    apartments.append(unsold_apartments_project)

    for _ in range(4):
        unsold_apartment = ApartmentDocumentFactory(
            project_ownership_type="Hitas",
            project_uuid=unsold_apartments_project.project_uuid,
        )
        apartments.append(unsold_apartment)

    sales_events = get_sold_state_events()

    project_uuids = [
        sold_apartments_project.project_uuid,
        unsold_apartments_project.project_uuid,
    ]

    export_service = XlsxSalesReportExportService(sales_events, project_uuids)
    export_service.get_rows()
    unsold_project_rows = export_service._get_project_rows(
        get_project(unsold_apartment.project_uuid),
        get_apartments(unsold_apartments_project.project_uuid, True),
        True,
    )

    assert len(unsold_project_rows) > 0

    # assert unsold apartments are calculated correctly
    assert export_service._get_total_sold_row(apartments) == [
        "Kaupat lukumäärä yhteensä",
        "",
        sell_count,
        0,
        len(apartments) - sell_count,
        "#E8E8E8",
    ]
    pass


@pytest.mark.django_db
def test_export_canceled_sales_should_not_count():
    apartments = []
    apartment = ApartmentDocumentFactory(project_ownership_type="Hitas")
    apartments.append(apartment)
    for _ in range(4):
        apartment = ApartmentDocumentFactory(
            project_ownership_type="Hitas", project_uuid=apartment.project_uuid
        )
        apartments.append(apartment)

    apartment_with_canceled_sale = apartments[0]
    sell_apartments(apartment_with_canceled_sale.project_uuid, len(apartments))

    # cancel the sale
    reservations = ApartmentReservation.objects.filter(
        apartment_uuid=apartment_with_canceled_sale.uuid
    ).order_by("id")
    reservations.last().set_state(ApartmentReservationState.RESERVED)
    cancel_reservation(
        reservations.last(),
        user=get_user_model().objects.first(),
    )

    # get state change events
    state_events = get_sold_state_events()
    export_service = XlsxSalesReportExportService(
        state_events, [apartment.project_uuid]
    )

    # we have one canceled sale so it shouldn't count as sold
    assert len(export_service._get_sold_apartments(apartments)) != len(apartments)


@pytest.mark.django_db
def test_export_sale_empty_ownership_type_should_not_crash():
    """Some projects might have empty project_ownership_type"""
    apartment = ApartmentDocumentFactory(project_ownership_type="Hitas")
    # ApartmentDocumentFactory doesn't allow us to create an ApartmentDocument with
    # an empty project_ownership_type so we'll need to set it manually
    apartment.project_ownership_type = None
    sold_events = get_sold_state_events()

    export_service = XlsxSalesReportExportService(sold_events, [apartment.project_uuid])

    try:
        export_service._is_haso(apartment)
        export_service._is_hitas(apartment)
    except AttributeError:
        pytest.fail("project_ownership == None case not handled properly")


@pytest.mark.django_db
def test_export_sale_report_new(
    elastic_hitas_project_with_5_apartments, elastic_haso_project_with_5_apartments
):
    sold_apartments_count = 4

    hitas_project, hitas_apartments = sell_apartments(
        elastic_hitas_project_with_5_apartments[0], sold_apartments_count
    )

    haso_project, haso_apartments = sell_apartments(
        elastic_haso_project_with_5_apartments[0], sold_apartments_count
    )

    all_apartments = [*hitas_apartments, *haso_apartments]

    # add event with non-existing apartment
    ApartmentReservationStateChangeEventFactory(
        state=ApartmentReservationState.SOLD,
        timestamp=timezone.now(),
    )
    ApartmentReservationStateChangeEventFactory(
        state=ApartmentReservationState.SOLD,
        timestamp=timezone.now(),
    )

    # add a duplicate SOLD-event for apartment
    reservation = ApartmentReservation.objects.filter().last()

    ApartmentReservationStateChangeEventFactory(
        state=ApartmentReservationState.SOLD,
        timestamp=timezone.now(),
        reservation=reservation,
    )
    ApartmentReservationStateChangeEventFactory(
        state=ApartmentReservationState.SOLD,
        timestamp=timezone.now(),
        reservation=reservation,
    )

    state_events = get_sold_state_events()

    export_service = XlsxSalesReportExportService(
        state_events,
        [hitas_apartments[0].project_uuid, haso_apartments[0].project_uuid],
    )

    # check that duplicate uuids are cleaned out
    duplicate_uuids = [
        uuid
        for uuid, count in collections.Counter(
            export_service.sold_apartment_uuids
        ).items()
        if count > 1
    ]

    assert len(duplicate_uuids) <= 0

    workbook = export_service.write_xlsx_file()

    assert isinstance(workbook, BytesIO)

    def get_sale_timestamp(apt: ApartmentDocument):
        event = state_events.get(reservation__apartment_uuid=apt.uuid)
        return event.timestamp.strftime("%d.%m.%Y")

    assert len(export_service._get_sold_apartments(hitas_apartments)) == 4

    # test project total calculations
    hitas_project_totals = export_service._get_project_totals(hitas_project)
    haso_project_totals = export_service._get_project_totals(haso_project)

    # hitas totals
    assert hitas_project_totals["sold_haso_apartments_count"] == 0
    assert hitas_project_totals["haso_right_of_occupancy_payment_sum"] == 0
    assert hitas_project_totals["sold_hitas_apartments_count"] == sold_apartments_count
    assert hitas_project_totals["unsold_apartments_count"] == (
        len(hitas_apartments) - sold_apartments_count
    )
    assert hitas_project_totals["hitas_sales_price_sum"] == export_service._sum_cents(
        [
            apt.sales_price
            for apt in export_service._get_sold_apartments(hitas_apartments)
        ]
    )
    assert hitas_project_totals[
        "hitas_debt_free_sales_price_sum"
    ] == export_service._sum_cents(
        [  # noqa: E501
            apt.debt_free_sales_price
            for apt in export_service._get_sold_apartments(hitas_apartments)
        ]
    )

    # haso totals
    assert haso_project_totals["sold_haso_apartments_count"] == sold_apartments_count
    assert haso_project_totals[
        "haso_right_of_occupancy_payment_sum"
    ] == export_service._sum_cents(
        [
            apt.right_of_occupancy_payment
            for apt in export_service._get_sold_apartments(haso_apartments)
        ]
    )
    assert haso_project_totals["sold_hitas_apartments_count"] == 0
    assert haso_project_totals["unsold_apartments_count"] == (
        len(hitas_apartments) - sold_apartments_count
    )
    assert haso_project_totals["hitas_sales_price_sum"] == 0
    assert haso_project_totals["hitas_debt_free_sales_price_sum"] == 0

    assert export_service._get_apartment_row(hitas_apartments[0]) == [
        hitas_apartments[0].apartment_number,
        Decimal(hitas_apartments[0].sales_price) / 100,
        Decimal(hitas_apartments[0].debt_free_sales_price) / 100,
        "",
        get_sale_timestamp(hitas_apartments[0]),
    ]

    assert export_service._get_apartment_row(haso_apartments[0]) == [
        haso_apartments[0].apartment_number,
        "",
        "",
        Decimal(haso_apartments[0].right_of_occupancy_payment) / 100,
        get_sale_timestamp(haso_apartments[0]),
    ]

    # assert that color formatting works
    # find rows starting with certain terms and check if the last index has a colour hex
    export_rows = export_service.get_rows()
    total_sum_row = export_service._get_total_sold_row(all_apartments)
    assert [r for r in export_rows if "Kohteen osoite" in r[0]][0][-1] == "#E8E8E8"
    assert total_sum_row[-1] == "#E8E8E8"
    assert [r for r in export_rows if "Kauppahinnat yhteensä" in r[0]][0][
        -1
    ] == "#E8E8E8"

    # Should not fail if apartment is selected but it has
    # no "SOLD"-events associated with it

    excluded_apartment = haso_apartments[0]
    # exclude one apartment's state events
    state_events = get_sold_state_events().exclude(
        reservation__apartment_uuid=excluded_apartment.uuid
    )
    export_service = XlsxSalesReportExportService(
        state_events, [haso_project.project_uuid, hitas_project.project_uuid]
    )

    # should not have a row if sold event was not found
    rows = export_service.get_rows()
    apartment_row_that_should_not_exist = export_service._get_apartment_row(
        excluded_apartment
    )

    assert apartment_row_that_should_not_exist not in rows

    # unsold count should not be affected by the given date range
    # i.e. don't calculate it from state change events
    # but from total apartments without 'sold' state

    expected_unsold_count = len(
        [
            apt
            for apt in all_apartments
            if (
                get_apartment_state_from_apartment_uuid(apt.uuid)
                != ApartmentReservationState.SOLD.value
            )
        ]
    )

    state_events_no_hitas_project = get_sold_state_events().exclude(
        reservation__apartment_uuid__in=[apt.uuid for apt in hitas_apartments]
    )

    export_service = XlsxSalesReportExportService(
        state_events_no_hitas_project,
        [haso_project.project_uuid, hitas_project.project_uuid],
    )

    assert export_service._get_unsold_count(all_apartments) == expected_unsold_count


@pytest.mark.django_db
def test_export_sale_report(
    elastic_hitas_project_with_5_apartments,
    elastic_haso_project_with_5_apartments,
):
    project_uuids = []
    for i in range(2):
        if i % 2 == 0:
            project_uuid, _ = elastic_hitas_project_with_5_apartments
        else:
            project_uuid, _ = elastic_haso_project_with_5_apartments
        apartment_uuids = get_apartment_uuids(project_uuid)
        for apartment_uuid in apartment_uuids:
            apt_app = ApplicationApartmentFactory.create_batch(
                2, apartment_uuid=apartment_uuid
            )
            add_application_to_queues(apt_app[0].application)
            add_application_to_queues(apt_app[1].application)
        distribute_apartments(project_uuid)
        project_uuids.append(project_uuid)

    # Now sold some apartment
    for project_uuid in project_uuids:
        # 1 apartment sold per project
        apartment_uuids = get_apartment_uuids(project_uuid)
        reservation = (
            ApartmentReservation.objects.filter(apartment_uuid=apartment_uuids[0])
            .reserved()
            .first()
        )
        reservation.set_state(ApartmentReservationState.SOLD)

    start = timezone.now() - timedelta(days=7)
    end = timezone.now() + timedelta(days=7)
    state_events = ApartmentReservationStateChangeEvent.objects.filter(
        state=ApartmentReservationState.SOLD, timestamp__range=[start, end]
    )
    assert state_events.count() == 2
    export_service = SaleReportExportService(state_events)
    csv_lines = export_service.get_rows()

    assert len(csv_lines) == 4
    for idx, header in enumerate(csv_lines[0]):
        assert header == SaleReportExportService.COLUMNS[idx][0]
    assert (csv_lines[1][1] == "" and csv_lines[1][2] == 1) or (
        csv_lines[1][1] == 1 and csv_lines[1][2] == ""
    )
    assert (csv_lines[2][1] == "" and csv_lines[2][2] == 1) or (
        csv_lines[2][1] == 1 and csv_lines[2][2] == ""
    )
    assert csv_lines[3][:3] == ["Total", 1, 1]


@pytest.mark.django_db
def test_csv_output(applicant_export_service):
    csv_lines = _split_csv(applicant_export_service.get_csv_string())
    assert csv_lines[0][0] == '"Primary applicant"'
    for idx, col in enumerate(ApplicantExportService.COLUMNS):
        assert csv_lines[0][idx] == f'"{col[0]}"'

    assert csv_lines[1][0] == '"{}"'.format(
        applicant_export_service.get_reservations()[
            0
        ].customer.primary_profile.full_name
    )


def _split_csv(csv_string):
    # split CSV into lines and columns without using the csv library
    csv_lines = csv_string.splitlines()
    return [line.split(";") for line in csv_lines]


@pytest.mark.django_db
def test_csv_non_ascii_characters(applicant_export_service):
    profile = applicant_export_service.get_reservations()[0].customer.primary_profile
    profile.first_name = "test"
    profile.last_name = "äöÄÖtest"
    profile.save()
    csv_lines = _split_csv(applicant_export_service.get_csv_string())
    assert csv_lines[1][0] == '"test äöÄÖtest"'


@pytest.mark.django_db
def test_write_csv_file(applicant_export_service, tmp_path):
    profile = applicant_export_service.get_reservations()[0].customer.primary_profile
    profile.first_name = "test äöÄÖtest"
    profile.save()
    output_file = tmp_path / "output.csv"
    applicant_export_service.write_csv_file(output_file)
    with open(output_file, encoding="utf-8-sig") as f:
        contents = f.read()
        assert contents.startswith('"Primary applicant";"Primary applicant address"')
        assert "äöÄÖtest" in contents
