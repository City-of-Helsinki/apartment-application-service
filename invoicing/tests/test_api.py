import datetime
import pytest
import uuid
from decimal import Decimal
from django.urls import reverse

from apartment.tests.factories import ApartmentDocumentFactory

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import ProjectInstallmentTemplate
from .factories import ProjectInstallmentTemplateFactory


@pytest.fixture
def apartment_document():
    project_uuid = uuid.uuid4()
    return ApartmentDocumentFactory(project_uuid=project_uuid)


@pytest.mark.django_db
def test_project_list_does_not_include_installments(
    apartment_document, profile_api_client
):
    ProjectInstallmentTemplateFactory()

    response = profile_api_client.get(reverse("apartment:project-list"), format="json")
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
def test_project_detail_installments_field_and_installments_endpoint_data(
    apartment_document, profile_api_client, target
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
        }
    )

    if target == "field":
        url = reverse("apartment:project-detail", kwargs={"project_uuid": project_uuid})
    else:
        url = reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        )

    response = profile_api_client.get(url, format="json")
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
def test_set_project_installments(apartment_document, profile_api_client):
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

    assert ProjectInstallmentTemplate.objects.count() == 1

    response = profile_api_client.post(
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
    apartment_document, profile_api_client
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

    response = profile_api_client.post(
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
    apartment_document, profile_api_client, input, expected_error
):
    project_uuid = apartment_document.project_uuid
    data = [input]

    response = profile_api_client.post(
        reverse(
            "apartment:project-installment-template-list",
            kwargs={"project_uuid": project_uuid},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert expected_error in str(response.data)
