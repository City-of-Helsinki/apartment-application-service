from datetime import timedelta
from typing import List

from apartment.elastic.documents import ApartmentDocument
from apartment.enums import OwnershipType
from application_form.tests.conftest import elastic_project_with_n_apartments
import pytest
from _pytest.fixtures import fixture
from django.utils import timezone

from apartment.elastic.queries import get_apartment, get_apartment_uuids, get_apartments, get_project
from application_form.enums import ApartmentReservationState
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
)
from application_form.services.export import (
    ApplicantExportService,
    ApplicantMailingListExportService,
    ProjectLotteryResultExportService,
    SaleReportExportService,
    XlsxSalesReportExportService,
)
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from customer.tests.factories import CustomerFactory
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
    csv_rows: List[List[str]], reservations: List[ApartmentReservation]
):
    for idx, header in enumerate(csv_rows[0]):
        assert header == ApplicantMailingListExportService.COLUMNS[idx][0]

    content_rows = csv_rows[1:]

    reservations = sorted(
        reservations, key=lambda x: get_apartment(x.apartment_uuid).apartment_number
    )

    for i, row in enumerate(content_rows):

        reservation = reservations[i]
        apartment = get_apartment(
            reservation.apartment_uuid, include_project_fields=True
        )

        expected_row = [
            apartment.apartment_number,
            reservation.queue_position,
            reservation.customer.primary_profile.first_name,
            reservation.customer.primary_profile.last_name,
            reservation.customer.primary_profile.email,
            reservation.customer.primary_profile.street_address,
            reservation.customer.primary_profile.postal_code,
            reservation.customer.primary_profile.city,
            reservation.customer.primary_profile.national_identification_number,
            reservation.customer.secondary_profile.first_name,
            reservation.customer.secondary_profile.last_name,
            reservation.customer.secondary_profile.email,
            reservation.customer.secondary_profile.street_address,
            reservation.customer.secondary_profile.postal_code,
            reservation.customer.secondary_profile.city,
            reservation.customer.secondary_profile.national_identification_number,
            bool(reservation.has_children),
            apartment.project_street_address,
            apartment.project_postal_code,
            apartment.project_city,
            apartment.apartment_structure,
            apartment.living_area,
        ]

        for expected_field_value, value in zip(expected_row, row):
            assert expected_field_value == value

    pass


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

    assert len(filtered_reservations) == 23
    assert len(csv_lines) == 24
    _validate_mailing_list_csv(csv_lines, filtered_reservations)


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

    assert csv_lines[1][3] is None
    assert (
        csv_lines[2][0]
        == applicant_export_service.get_reservations()[
            1
        ].customer.primary_profile.full_name
    )
    assert csv_lines[2][3] is None


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


@pytest.mark.django_db
def test_export_sale_report_new(
    elastic_hitas_project_with_5_apartments,
    elastic_haso_project_with_5_apartments,
):
    projects = []
    projects_apartments = {}

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

        projects.append(
            get_project(project_uuid)
        )

    # Now sold some apartment
    for project in projects:
        # 1 apartment sold per project
        apartments = get_apartments(project.project_uuid)
        reservation = (
            ApartmentReservation.objects.filter(apartment_uuid=apartments[0].uuid)
            .reserved()
            .first()
        )
        reservation.set_state(ApartmentReservationState.SOLD)
        projects_apartments[project.project_uuid] = apartments

    start = timezone.now() - timedelta(days=7)
    end = timezone.now() + timedelta(days=7)
    state_events = ApartmentReservationStateChangeEvent.objects.filter(
        state=ApartmentReservationState.SOLD, timestamp__range=[start, end]
    )

    export_service = XlsxSalesReportExportService(state_events)
    export_rows = export_service.get_rows()

    hitas_project = projects[0]
    hitas_apartments = projects_apartments[hitas_project.project_uuid]

    haso_project = projects[1]
    haso_apartments = projects_apartments[haso_project.project_uuid]

    def get_sale_timestamp(apt: ApartmentDocument): 
        event = state_events.get(reservation__apartment_uuid=apt.uuid)
        return event.timestamp.strftime("%d.%m.%Y")

    expected_rows = [
        [ "Project address", "Apartments total", "Sold HITAS apartments", "Sold HASO apartments", "Unsold apartments", ],
        [
            hitas_project.project_street_address,
            5,
            1,
            "",
            4
        ],
        ["Huoneisto", "Myyntihinta", "Velaton hinta", "Luovutushinta", "Kaupantekopäivä"],
        [
            hitas_apartments[0].apartment_number,
            hitas_apartments[0].sales_price,
            hitas_apartments[0].debt_free_sales_price,
            "",
            get_sale_timestamp(hitas_apartments[0])
        ],
        [
            "Yhteensä",
            hitas_apartments[0].sales_price,
            hitas_apartments[0].debt_free_sales_price,
            "",
        ],
        [""*5],
        [ 
            haso_project.project_street_address,
            5,
            "",
            1,
            4
        ],
        [
            haso_apartments[0].apartment_number,
            "",
            "",
            haso_apartments[0].right_of_occupancy_payment,
            get_sale_timestamp(haso_apartments[0]),
        ],
        [
            "Yhteensä",
            "",
            "",
            haso_apartments[0].right_of_occupancy_payment,
        ],
        [""],
        [""],
        [""],
        [
            "Kaupat lukumäärä yhteensä", 
            "",
            1,
            1,
            8
        ],
        [
            "Kauppahinnat yhteensä",
            hitas_apartments[0].sales_price,
            hitas_apartments[0].debt_free_sales_price,
            haso_apartments[0].right_of_occupancy_payment
        ]
    ]
    
    assert export_rows == expected_rows

    
    # assert state_events.count() == 2
    # export_service = SaleReportExportService(state_events)
    # csv_lines = export_service.get_rows()

    # assert len(csv_lines) == 4
    # for idx, header in enumerate(csv_lines[0]):
    #     assert header == SaleReportExportService.COLUMNS[idx][0]
    # assert (csv_lines[1][1] == "" and csv_lines[1][2] == 1) or (
    #     csv_lines[1][1] == 1 and csv_lines[1][2] == ""
    # )
    # assert (csv_lines[2][1] == "" and csv_lines[2][2] == 1) or (
    #     csv_lines[2][1] == 1 and csv_lines[2][2] == ""
    # )
    # assert csv_lines[3][:3] == ["Total", 1, 1]



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
