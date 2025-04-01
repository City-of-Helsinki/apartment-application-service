import datetime
import logging
import uuid
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import ApartmentInstallment, ProjectInstallmentTemplate
from .factories import (
    ApartmentInstallmentFactory,
    InstallmentBaseFactory,
    PaymentFactory,
    ProjectInstallmentTemplateFactory,
)

_logger = logging.getLogger()


@pytest.fixture
def apartment_document():
    project_uuid = uuid.uuid4()
    return ApartmentDocumentFactory(project_uuid=project_uuid)


@pytest.fixture
def reservation_with_installments():
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.PAYMENT_1,
            "value": "1000.00",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
        },
    )
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.55",
            "account_number": "123123123-123",
            "reference_number": "REFERENCE-321",
        },
    )
    return reservation


@pytest.mark.django_db
def test_project_list_does_not_include_installments(
    apartment_document, sales_ui_salesperson_api_client
):
    ProjectInstallmentTemplateFactory()

    response = sales_ui_salesperson_api_client.get(
        reverse("apartment:project-list"), format="json"
    )
    assert response.status_code == 200
    assert "installment_templates" not in response.data[0]


@pytest.mark.django_db
def test_project_detail_installments_percentage_specifier_refund_right_of_occupancy(
    apartment_document, sales_ui_salesperson_api_client
):
    project_uuid = apartment_document.project_uuid

    url = reverse(
        "apartment:project-installment-template-list",
        kwargs={"project_uuid": project_uuid},
    )

    # use variable to keep line length short and the linter happy
    percentage_specifier = InstallmentPercentageSpecifier.RIGHT_OF_OCCUPANCY_PAYMENT
    data = [
        {
            "type": "REFUND",
            "amount": 20,
            "account_number": "123123123-123",
            "due_date": None,
            "percentage_specifier": percentage_specifier.value,
        },
        {
            "type": "REFUND_2",
            "amount": 20,
            "account_number": "123123123-123",
            "due_date": None,
            "percentage_specifier": percentage_specifier.value,
        },
        {
            "type": "REFUND_3",
            "amount": 20,
            "account_number": "123123123-123",
            "due_date": None,
            "percentage_specifier": percentage_specifier.value,
        },
        {
            "type": "RIGHT_OF_OCCUPANCY_PAYMENT_1",
            "amount": 20,
            "account_number": "123123123-123",
            "due_date": None,
            "percentage_specifier": percentage_specifier.value,
        },
        {
            "type": "RIGHT_OF_OCCUPANCY_PAYMENT_2",
            "amount": 20,
            "account_number": "123123123-123",
            "due_date": None,
            "percentage_specifier": percentage_specifier.value,
        },
        {
            "type": "RIGHT_OF_OCCUPANCY_PAYMENT_3",
            "amount": 20,
            "account_number": "123123123-123",
            "due_date": None,
            "percentage_specifier": percentage_specifier.value,
        },
    ]

    response = sales_ui_salesperson_api_client.post(url, data=data, format="json")
    assert len(response.json()) == 6
    pass


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target",
    [
        "field",
        "endpoint",
    ],
)
def test_project_detail_installments_field_and_endpoint_data_unauthorized(
    apartment_document, user_api_client, target
):
    project_uuid = apartment_document.project_uuid
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.PAYMENT_1,
            "value": "53.5",
            "unit": InstallmentUnit.PERCENT,
            "percentage_specifier": InstallmentPercentageSpecifier.SALES_PRICE,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
    )
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.00",
            "unit": InstallmentUnit.EURO,
            "account_number": "123123123-123",
            "due_date": None,
        },
    )

    if target == "field":
        url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})
    else:
        url = reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        )

    response = user_api_client.get(url, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target",
    [
        "field",
        "endpoint",
    ],
)
def test_project_detail_installments_field_and_installments_endpoint_data(
    apartment_document, sales_ui_salesperson_api_client, target
):
    project_uuid = apartment_document.project_uuid
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.PAYMENT_1,
            "value": "53.5",
            "unit": InstallmentUnit.PERCENT,
            "percentage_specifier": InstallmentPercentageSpecifier.SALES_PRICE,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
    )
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.00",
            "unit": InstallmentUnit.EURO,
            "account_number": "123123123-123",
            "due_date": None,
        },
    )
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.REFUND_2,
            "value": "100.00",
            "unit": InstallmentUnit.EURO,
            "account_number": "123123123-123",
            "due_date": None,
        },
    )
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.REFUND_3,
            "value": "100.00",
            "unit": InstallmentUnit.EURO,
            "account_number": "123123123-123",
            "due_date": None,
        },
    )

    if target == "field":
        url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})
    else:
        url = reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        )

    response = sales_ui_salesperson_api_client.get(url, format="json")
    assert response.status_code == 200

    if target == "field":
        data = response.data["installment_templates"]
    else:
        data = response.data

    assert data == [
        {
            "type": "PAYMENT_1",
            "percentage": "53.5",
            "percentage_specifier": "SALES_PRICE",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
        {
            "type": "REFUND",
            "amount": 10000,
            "account_number": "123123123-123",
            "due_date": None,
        },
        {
            "type": "REFUND_2",
            "amount": 10000,
            "account_number": "123123123-123",
            "due_date": None,
        },
        {
            "type": "REFUND_3",
            "amount": 10000,
            "account_number": "123123123-123",
            "due_date": None,
        },
    ]


@pytest.mark.django_db
def test_set_project_installments_unauthorized(apartment_document, user_api_client):
    # InstallmentBaseFactory uses a sequence to cycle through Installment types
    # This sequence number doesn't reset after each test case which leads to
    # tests dependent on generated installments having a certain type failing
    # when new calls to InstallmentBaseFactory subclasses are added (or removed).
    # Resetting the sequence number here helps keep the types consistent
    InstallmentBaseFactory.reset_sequence(0)

    project_uuid = apartment_document.project_uuid
    data = [
        {
            "type": "PAYMENT_1",
            "percentage": "53.5",
            "percentage_specifier": "SALES_PRICE",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
        {
            "type": "REFUND",
            "amount": 10000,
            "account_number": "123123123-123",
            "due_date": None,
        },
    ]

    response = user_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.parametrize("has_old_installments", (False, True))
@pytest.mark.django_db
def test_set_project_installments(
    sales_ui_salesperson_api_client, has_old_installments
):
    apartment_document = ApartmentDocumentFactory(
        uuid=uuid.uuid4(), project_ownership_type="Hitas"
    )

    project_uuid = apartment_document.project_uuid
    data = [
        {
            "type": "PAYMENT_1",
            "percentage": "53.5",
            "percentage_specifier": "SALES_PRICE",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
        {
            "type": "PAYMENT_2",
            "percentage_specifier": "SALES_PRICE_FLEXIBLE",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
        {
            "type": "REFUND",
            "amount": 10000,
            "account_number": "123123123-123",
            "due_date": None,
        },
    ]

    # just to make sure other projects' installment templates aren't affected
    other_project_installment_template = ProjectInstallmentTemplateFactory()

    if has_old_installments:
        ProjectInstallmentTemplateFactory.create_batch(2, project_uuid=project_uuid)

    assert (
        ProjectInstallmentTemplate.objects.count() == 3 if has_old_installments else 1
    )

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201

    assert ProjectInstallmentTemplate.objects.count() == 4
    assert (
        ProjectInstallmentTemplate.objects.exclude(
            project_uuid=other_project_installment_template.project_uuid
        ).count()
        == 3
    )

    installment_templates = ProjectInstallmentTemplate.objects.order_by("id")
    installment_1, installment_2, installment_3 = installment_templates[1:]

    assert installment_1.type == InstallmentType.PAYMENT_1
    assert installment_1.value == Decimal("53.50")
    assert installment_1.unit == InstallmentUnit.PERCENT
    assert (
        installment_1.percentage_specifier == InstallmentPercentageSpecifier.SALES_PRICE
    )
    assert installment_1.account_number == "123123123-123"
    assert installment_1.due_date == datetime.date(2022, 2, 19)

    assert installment_2.type == InstallmentType.PAYMENT_2
    assert installment_2.value == Decimal("0.00")
    assert (
        installment_2.percentage_specifier
        == InstallmentPercentageSpecifier.SALES_PRICE_FLEXIBLE
    )
    assert installment_2.account_number == "123123123-123"
    assert installment_2.due_date == datetime.date(2022, 2, 19)

    assert installment_3.type == InstallmentType.REFUND
    assert installment_3.value == Decimal("100.00")
    assert installment_3.unit == InstallmentUnit.EURO
    assert installment_3.percentage_specifier is None
    assert installment_3.account_number == "123123123-123"
    assert installment_3.due_date is None


@pytest.mark.django_db
def test_set_project_installments_percentage_specifier_required_for_percentages(
    apartment_document, sales_ui_salesperson_api_client
):
    project_uuid = apartment_document.project_uuid
    data = [
        {
            "type": "PAYMENT_1",
            "percentage": "53.5",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        }
    ]

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert "specifier" in str(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input, expected_error",
    [
        (
            {
                "type": "PAYMENT_1",
                "percentage_specifier": "SALES_PRICE",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
            },
            "Either amount or percentage is required but not both.",
        ),
        (
            {
                "type": "PAYMENT_1",
                "amount": 1500,
                "percentage": "53.5",
                "percentage_specifier": "SALES_PRICE",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
            },
            "Either amount or percentage is required but not both.",
        ),
        (
            {
                "type": "PAYMENT_1",
                "percentage": "53.5",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
            },
            "percentage_specifier is required when providing percentage.",
        ),
        (
            {
                "type": "RIGHT_OF_OCCUPANCY_PAYMENT_1",
                "percentage": "53.5",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
                "percentage_specifier": "RIGHT_OF_OCCUPANCY_PAYMENT",
            },
            "Cannot select RIGHT_OF_OCCUPANCY_PAYMENT as unit specifier in "
            "HITAS payment template",
        ),
        (
            {
                "type": "RIGHT_OF_OCCUPANCY_PAYMENT_2",
                "percentage": "53.5",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
                "percentage_specifier": "RIGHT_OF_OCCUPANCY_PAYMENT",
            },
            "Cannot select RIGHT_OF_OCCUPANCY_PAYMENT as unit specifier in "
            "HITAS payment template",
        ),
        (
            {
                "type": "RIGHT_OF_OCCUPANCY_PAYMENT_3",
                "percentage": "53.5",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
                "percentage_specifier": "RIGHT_OF_OCCUPANCY_PAYMENT",
            },
            "Cannot select RIGHT_OF_OCCUPANCY_PAYMENT as unit specifier in "
            "HITAS payment template",
        ),
        (
            {
                "type": "PAYMENT_1",
                "percentage": "53.5",
                "account_number": "123123123-123",
                "due_date": "2022-02-19",
                "percentage_specifier": "SALES_PRICE",
            },
            "Cannot select SALES_PRICE as unit specifier in HASO payment template",
        ),
    ],
)
def test_set_project_installments_errors(
    apartment_document, sales_ui_salesperson_api_client, input, expected_error
):
    if "RIGHT_OF_OCCUPANCY_PAYMENT" in input.get("percentage_specifier", ""):
        apartment_document = ApartmentDocumentFactory(
            uuid=uuid.uuid4(), project_ownership_type="Hitas"
        )
    if input.get("percentage_specifier") == "SALES_PRICE":
        apartment_document = ApartmentDocumentFactory(
            uuid=uuid.uuid4(), project_ownership_type="Haso"
        )
    project_uuid = apartment_document.project_uuid
    data = [input]

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
    # import ipdb;ipdb.set_trace()
    assert response.status_code == 400
    assert expected_error in str(response.data)


@pytest.mark.django_db
def test_apartment_installments_endpoint_unauthorized(
    apartment_document, user_api_client
):
    reservation = ApartmentReservationFactory()
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.PAYMENT_1,
            "value": "1000.00",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
        },
    )
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.55",
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
        },
    )

    url = reverse(
        "application_form:apartment-installment-list",
        kwargs={"apartment_reservation_id": reservation.id},
    )
    response = user_api_client.get(url, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_apartment_installments_endpoint_data(
    apartment_document, sales_ui_salesperson_api_client
):
    reservation = ApartmentReservationFactory()
    installment_1 = ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.PAYMENT_1,
            "value": "1000.00",
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
        },
    )
    PaymentFactory(
        apartment_installment=installment_1,
        amount=1,
        payment_date=installment_1.due_date,
    )
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.55",
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
        },
    )

    url = reverse(
        "application_form:apartment-installment-list",
        kwargs={"apartment_reservation_id": reservation.id},
    )
    response = sales_ui_salesperson_api_client.get(url, format="json")

    assert response.status_code == 200
    assert response.data == [
        {
            "type": "PAYMENT_1",
            "amount": 100000,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
            "added_to_be_sent_to_sap_at": None,
            "payment_state": {
                "status": "UNDERPAID",
                "is_overdue": True,
            },
            "payments": [
                {
                    "amount": 100,
                    "payment_date": "2022-02-19",
                }
            ],
        },
        {
            "type": "REFUND",
            "amount": 10055,
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
            "added_to_be_sent_to_sap_at": None,
            "payment_state": {
                "status": "UNPAID",
                "is_overdue": False,
            },
            "payments": [],
        },
    ]


@pytest.mark.parametrize("has_old_installments", (False, True))
@pytest.mark.django_db
def test_set_apartment_installments(
    sales_ui_salesperson_api_client, has_old_installments
):
    InstallmentBaseFactory.reset_sequence(0)
    reservation = ApartmentReservationFactory()

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 100055,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
            "added_to_be_sent_to_sap_at": timezone.now(),
        },
        {  # Test DB isn't cleared between test cases, use REFUND_2 to avoid collisions until then  # noqa: E501
            "type": "REFUND",
            "amount": 0,
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
            "added_to_be_sent_to_sap_at": timezone.now(),
        },
    ]

    # just to make sure other reservations' installments aren't affected
    other_reservation_installment = ApartmentInstallmentFactory()

    if has_old_installments:
        ApartmentInstallmentFactory.create_batch(2, apartment_reservation=reservation)

    assert ApartmentInstallment.objects.count() == 3 if has_old_installments else 1

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201

    installments = ApartmentInstallment.objects.order_by("id")
    installment_1, installment_2 = installments[1:]

    data[0]["reference_number"] = installment_1.reference_number
    data[1]["reference_number"] = installment_2.reference_number
    data[0]["added_to_be_sent_to_sap_at"] = None
    data[1]["added_to_be_sent_to_sap_at"] = None
    response_data = response.data.copy()
    response_data[0].pop("payment_state")
    response_data[0].pop("payments")
    response_data[1].pop("payment_state")
    response_data[1].pop("payments")

    assert response_data == data

    assert ApartmentInstallment.objects.count() == 3
    assert (
        ApartmentInstallment.objects.exclude(
            id=other_reservation_installment.id
        ).count()
        == 2
    )

    assert installment_1.type == InstallmentType.PAYMENT_1
    assert installment_1.value == Decimal("1000.55")
    assert installment_1.account_number == "123123123-123"
    assert installment_1.due_date == datetime.date(2022, 2, 19)

    assert installment_2.type == InstallmentType.REFUND
    assert installment_2.value == Decimal("0")
    assert installment_2.account_number == "123123123-123"
    assert installment_2.due_date is None


@pytest.mark.django_db
def test_cannot_edit_installments_already_sent_to_sap(sales_ui_salesperson_api_client):
    reservation = ApartmentReservationFactory()

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 100055,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        }
    ]

    old_installments = [
        ApartmentInstallmentFactory.create(
            apartment_reservation=reservation,
            type=InstallmentType.PAYMENT_1,
            value=12345,
            account_number="007",
            due_date=datetime.date(2022, 1, 1),
            added_to_be_sent_to_sap_at=timezone.now(),
        ),
        ApartmentInstallmentFactory.create(
            apartment_reservation=reservation,
            type=InstallmentType.PAYMENT_2,
            value=54321,
            account_number="008",
            due_date=datetime.date(2022, 2, 2),
            added_to_be_sent_to_sap_at=timezone.now(),
        ),
    ]

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201

    assert ApartmentInstallment.objects.count() == 2
    new_installments = ApartmentInstallment.objects.order_by("id")

    for new_installment, old_installment in zip(new_installments, old_installments):
        for field in (
            "id",
            "type",
            "value",
            "account_number",
            "invoice_number",
            "due_date",
        ):
            assert getattr(new_installment, field) == getattr(old_installment, field)


@pytest.mark.parametrize("reference_number_given", (False, True))
@pytest.mark.django_db
def test_apartment_installment_reference_number_populating(
    sales_ui_salesperson_api_client, reference_number_given
):
    reservation = ApartmentReservationFactory()

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 100000,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        }
    ]

    if reference_number_given:
        data[0]["reference_number"] = "THIS-SHOULD-BE-IGNORED"

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )

    assert response.data[0]["reference_number"].startswith("2825")
    assert (
        ApartmentInstallment.objects.first().reference_number
        == response.data[0]["reference_number"]
    )


@pytest.mark.parametrize("reference_number_given", (False, True))
@pytest.mark.django_db
def test_apartment_installment_reference_number_populating_on_update(
    sales_ui_salesperson_api_client, reference_number_given
):
    original_reference_number = "ORIGINAL-REFERENCE-NUMBER"
    reservation = ApartmentReservationFactory()
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        type=InstallmentType.PAYMENT_1,
        reference_number=original_reference_number,
    )

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 100000,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
        },
    ]

    if reference_number_given:
        data[0]["reference_number"] = "THIS-SHOULD-BE-IGNORED"

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )

    # original reference number should be kept because the same installment
    # (type PAYMENT_1 matches) is updated
    assert response.data[0]["reference_number"] == original_reference_number
    assert (
        ApartmentInstallment.objects.first().reference_number
        == original_reference_number
    )

    data = [
        {
            "type": "PAYMENT_2",
            "amount": 200000,
            "account_number": "124123123-123",
            "due_date": "2023-02-19",
        },
    ]

    if reference_number_given:
        data[0]["reference_number"] = "THIS-SHOULD-BE-IGNORED"

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )

    # original reference number should NOT be kept because another installment type is
    # used here
    assert response.data[0]["reference_number"] != original_reference_number
    assert (
        ApartmentInstallment.objects.first().reference_number
        != original_reference_number
    )

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 300000,
            "account_number": "125123123-123",
            "due_date": "2024-02-19",
        },
    ]

    if reference_number_given:
        data[0]["reference_number"] = "THIS-SHOULD-BE-IGNORED"

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )

    # the type is the same as at start, but because the installment PAYMENT_1 was
    # deleted in the middle, it should now have a new reference number
    assert response.data[0]["reference_number"] != original_reference_number
    assert (
        ApartmentInstallment.objects.first().reference_number
        != original_reference_number
    )


@pytest.mark.django_db
def test_apartment_installment_invoice_pdf_unauthorized(
    user_api_client, reservation_with_installments
):
    response = user_api_client.get(
        reverse(
            "application_form:apartment-installment-invoice",
            kwargs={"apartment_reservation_id": reservation_with_installments.id},
        ),
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_apartment_installment_invoice_pdf(
    sales_ui_salesperson_api_client, reservation_with_installments
):
    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:apartment-installment-invoice",
            kwargs={"apartment_reservation_id": reservation_with_installments.id},
        ),
        format="json",
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert (
        bytes(
            reservation_with_installments.customer.primary_profile.full_name,
            encoding="utf-8",
        )
        in response.content
    )


@pytest.mark.django_db
def test_apartment_installment_invoice_pdf_filtering(
    sales_ui_salesperson_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-invoice",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = sales_ui_salesperson_api_client.get(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content
    one_installment_invoice = response.content

    response = sales_ui_salesperson_api_client.get(
        base_url + "?types=PAYMENT_1,REFUND",
        format="json",
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content
    two_installment_invoice = response.content

    assert len(two_installment_invoice) > len(one_installment_invoice)


@pytest.mark.parametrize("types_param", ("PAYMENT_5", "xxx"))
@pytest.mark.django_db
def test_apartment_installment_invoice_pdf_filtering_errors(
    sales_ui_salesperson_api_client, reservation_with_installments, types_param
):
    base_url = reverse(
        "application_form:apartment-installment-invoice",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = sales_ui_salesperson_api_client.get(
        base_url + "?types={types_param}",
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_add_installments_to_be_sent_to_sap_at_unauthorized(
    user_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = user_api_client.post(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_add_installments_to_be_sent_to_sap_at(
    sales_ui_salesperson_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = sales_ui_salesperson_api_client.post(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 200

    assert response.data[0].keys() == {
        "account_number",
        "due_date",
        "reference_number",
        "type",
        "amount",
        "added_to_be_sent_to_sap_at",
        "payment_state",
        "payments",
    }

    assert response.data[0]["added_to_be_sent_to_sap_at"]
    assert reservation_with_installments.apartment_installments.order_by("id")[
        0
    ].added_to_be_sent_to_sap_at
    assert not response.data[1]["added_to_be_sent_to_sap_at"]
    assert not (
        reservation_with_installments.apartment_installments.order_by("id")[
            1
        ].added_to_be_sent_to_sap_at
    )


@pytest.mark.django_db
def test_add_installments_to_be_sent_to_sap_at_already_added(
    sales_ui_salesperson_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = sales_ui_salesperson_api_client.post(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 200

    response = sales_ui_salesperson_api_client.post(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 400
    assert "already" in str(response.data)


@pytest.mark.django_db
def test_set_apartment_installments_generate_metadata(
    sales_ui_salesperson_api_client,
):
    reservation = ApartmentReservationFactory()

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 100055,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
            "added_to_be_sent_to_sap_at": timezone.now(),
        },
        {
            "type": "REFUND",
            "amount": 0,
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
            "added_to_be_sent_to_sap_at": timezone.now(),
        },
    ]

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201
    installments = ApartmentInstallment.objects.all()
    assert len(installments) == 2
    user = sales_ui_salesperson_api_client.user
    expected_handler = f"{user.first_name} {user.last_name}".strip()
    assert installments[0].handler == expected_handler
    assert installments[1].handler == expected_handler


@pytest.mark.django_db
def test_apartment_installment_refund_value_cannot_be_positive(
    sales_ui_salesperson_api_client,
):
    reservation = ApartmentReservationFactory()

    data = [
        {
            "type": "REFUND",
            "amount": 1,  # illegal positive value
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
        },
    ]

    response = sales_ui_salesperson_api_client.post(
        reverse(
            "application_form:apartment-installment-list",
            kwargs={"apartment_reservation_id": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert "positive" in str(response.data)
