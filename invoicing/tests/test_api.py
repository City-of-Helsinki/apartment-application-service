import datetime
import pytest
import uuid
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import ApartmentReservationFactory

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import ApartmentInstallment, ProjectInstallmentTemplate
from .factories import ApartmentInstallmentFactory, ProjectInstallmentTemplateFactory


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
        }
    )
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.55",
            "account_number": "123123123-123",
            "reference_number": "REFERENCE-321",
        }
    )
    return reservation


@pytest.mark.django_db
def test_project_list_does_not_include_installments(
    apartment_document, salesperson_api_client
):
    ProjectInstallmentTemplateFactory()

    response = salesperson_api_client.get(
        reverse("apartment:project-list"), format="json"
    )
    assert response.status_code == 200
    assert "installment_templates" not in response.data[0]


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
        }
    )
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.00",
            "unit": InstallmentUnit.EURO,
            "account_number": "123123123-123",
            "due_date": None,
        }
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
    apartment_document, salesperson_api_client, target
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
        }
    )
    ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.00",
            "unit": InstallmentUnit.EURO,
            "account_number": "123123123-123",
            "due_date": None,
        }
    )

    if target == "field":
        url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})
    else:
        url = reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        )

    response = salesperson_api_client.get(url, format="json")
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
    ]


@pytest.mark.django_db
def test_set_project_installments_unauthorized(apartment_document, user_api_client):
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
    apartment_document, salesperson_api_client, has_old_installments
):
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

    # just to make sure other projects' installment templates aren't affected
    other_project_installment_template = ProjectInstallmentTemplateFactory()

    if has_old_installments:
        ProjectInstallmentTemplateFactory.create_batch(2, project_uuid=project_uuid)

    assert (
        ProjectInstallmentTemplate.objects.count() == 3 if has_old_installments else 1
    )

    response = salesperson_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201
    assert response.data == data

    assert ProjectInstallmentTemplate.objects.count() == 3
    assert (
        ProjectInstallmentTemplate.objects.exclude(
            project_uuid=other_project_installment_template.project_uuid
        ).count()
        == 2
    )

    installment_templates = ProjectInstallmentTemplate.objects.order_by("id")
    installment_1, installment_2 = installment_templates[1:]

    assert installment_1.type == InstallmentType.PAYMENT_1
    assert installment_1.value == Decimal("53.50")
    assert installment_1.unit == InstallmentUnit.PERCENT
    assert (
        installment_1.percentage_specifier == InstallmentPercentageSpecifier.SALES_PRICE
    )
    assert installment_1.account_number == "123123123-123"
    assert installment_1.due_date == datetime.date(2022, 2, 19)

    assert installment_2.type == InstallmentType.REFUND
    assert installment_2.value == Decimal("100.00")
    assert installment_2.unit == InstallmentUnit.EURO
    assert installment_2.percentage_specifier is None
    assert installment_2.account_number == "123123123-123"
    assert installment_2.due_date is None


@pytest.mark.django_db
def test_set_project_installments_percentage_specifier_required_for_percentages(
    apartment_document, salesperson_api_client
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

    response = salesperson_api_client.post(
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
    ],
)
def test_set_project_installments_errors(
    apartment_document, salesperson_api_client, input, expected_error
):
    project_uuid = apartment_document.project_uuid
    data = [input]

    response = salesperson_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
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
        }
    )
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.55",
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
        }
    )

    url = reverse(
        "application_form:apartment-installment-list",
        kwargs={"apartment_reservation_id": reservation.id},
    )
    response = user_api_client.get(url, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_apartment_installments_endpoint_data(
    apartment_document, salesperson_api_client
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
        }
    )
    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        **{
            "type": InstallmentType.REFUND,
            "value": "100.55",
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
        }
    )

    url = reverse(
        "application_form:apartment-installment-list",
        kwargs={"apartment_reservation_id": reservation.id},
    )
    response = salesperson_api_client.get(url, format="json")

    assert response.status_code == 200
    assert response.data == [
        {
            "type": "PAYMENT_1",
            "amount": 100000,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
            "added_to_be_sent_to_sap_at": None,
        },
        {
            "type": "REFUND",
            "amount": 10055,
            "account_number": "123123123-123",
            "due_date": None,
            "reference_number": "REFERENCE-321",
            "added_to_be_sent_to_sap_at": None,
        },
    ]


@pytest.mark.parametrize("has_old_installments", (False, True))
@pytest.mark.django_db
def test_set_apartment_installments(salesperson_api_client, has_old_installments):
    reservation = ApartmentReservationFactory()

    data = [
        {
            "type": "PAYMENT_1",
            "amount": 100000,
            "account_number": "123123123-123",
            "due_date": "2022-02-19",
            "reference_number": "REFERENCE-123",
            "added_to_be_sent_to_sap_at": timezone.now(),
        },
        {
            "type": "REFUND",
            "amount": 10055,
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

    response = salesperson_api_client.post(
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
    assert response.data == data

    assert ApartmentInstallment.objects.count() == 3
    assert (
        ApartmentInstallment.objects.exclude(
            id=other_reservation_installment.id
        ).count()
        == 2
    )

    assert installment_1.type == InstallmentType.PAYMENT_1
    assert installment_1.value == Decimal("1000.00")
    assert installment_1.account_number == "123123123-123"
    assert installment_1.due_date == datetime.date(2022, 2, 19)

    assert installment_2.type == InstallmentType.REFUND
    assert installment_2.value == Decimal("100.55")
    assert installment_2.account_number == "123123123-123"
    assert installment_2.due_date is None


@pytest.mark.parametrize("reference_number_given", (False, True))
@pytest.mark.django_db
def test_apartment_installment_reference_number_populating(
    salesperson_api_client, reference_number_given
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

    response = salesperson_api_client.post(
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
    salesperson_api_client, reference_number_given
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

    response = salesperson_api_client.post(
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

    response = salesperson_api_client.post(
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

    response = salesperson_api_client.post(
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
    salesperson_api_client, reservation_with_installments
):
    response = salesperson_api_client.get(
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
    salesperson_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-invoice",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = salesperson_api_client.get(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content
    one_installment_invoice = response.content

    response = salesperson_api_client.get(
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
    salesperson_api_client, reservation_with_installments, types_param
):
    base_url = reverse(
        "application_form:apartment-installment-invoice",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = salesperson_api_client.get(
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
    salesperson_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = salesperson_api_client.post(
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
    salesperson_api_client, reservation_with_installments
):
    base_url = reverse(
        "application_form:apartment-installment-add-to-be-sent-to-sap",
        kwargs={"apartment_reservation_id": reservation_with_installments.id},
    )

    response = salesperson_api_client.post(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 200

    response = salesperson_api_client.post(
        base_url + "?types=PAYMENT_1",
        format="json",
    )
    assert response.status_code == 400
    assert "already" in str(response.data)
