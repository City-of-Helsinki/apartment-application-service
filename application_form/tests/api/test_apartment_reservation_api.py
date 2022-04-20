import pytest
import uuid
from datetime import date
from decimal import Decimal
from django.urls import reverse

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import ApartmentReservationState
from application_form.tests.factories import ApartmentReservationFactory
from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
)
from invoicing.tests.factories import (
    ApartmentInstallmentFactory,
    ProjectInstallmentTemplateFactory,
)


@pytest.mark.django_db
def test_root_apartment_reservation_detail(
    api_client, elastic_project_with_5_apartments
):
    _, apartments = elastic_project_with_5_apartments
    reservation = ApartmentReservationFactory(apartment_uuid=apartments[0].uuid)
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)

    response = api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 200

    assert response.data == {
        "id": reservation.id,
        "installments": [
            {
                "type": installment.type.value,
                "amount": int(installment.value * 100),
                "account_number": installment.account_number,
                "reference_number": installment.reference_number,
                "due_date": None,
            }
        ],
        "installment_candidates": [],
        "apartment_uuid": reservation.apartment_uuid,
        "queue_position": reservation.queue_position,
        "state": reservation.state.value,
        "lottery_position": None,
    }


@pytest.mark.django_db
def test_root_apartment_reservation_detail_installment_candidates(api_client):
    apartment = ApartmentDocumentFactory(
        sales_price=12345678, debt_free_sales_price=9876543  # 123456,78e and 98765,43e
    )
    project_uuid = apartment.project_uuid
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    installment_template_1 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.REFUND,
        value=Decimal("100.50"),
        unit=InstallmentUnit.EURO,
        due_date=date(2022, 1, 10),
    )
    installment_template_2 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.PAYMENT_1,
        value=Decimal("10"),
        unit=InstallmentUnit.PERCENT,
        percentage_specifier=InstallmentPercentageSpecifier.SALES_PRICE,
    )
    installment_template_3 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.PAYMENT_2,
        value=Decimal("0.7"),
        unit=InstallmentUnit.PERCENT,
        percentage_specifier=InstallmentPercentageSpecifier.DEBT_FREE_SALES_PRICE,
    )
    installment_template_4 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.PAYMENT_3,
        value=Decimal("17.25"),
        unit=InstallmentUnit.PERCENT,
        percentage_specifier=InstallmentPercentageSpecifier.DEBT_FREE_SALES_PRICE_FLEXIBLE,  # noqa: E501
    )
    # another project
    ProjectInstallmentTemplateFactory(
        project_uuid=uuid.UUID("19867533-2a60-4b3f-b166-f13af513d2d2"),
        type=InstallmentType.PAYMENT_1,
        value=Decimal("53"),
        unit=InstallmentUnit.EURO,
    )

    response = api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 200

    installment_candidates = response.data["installment_candidates"]
    assert len(installment_candidates) == 4

    assert installment_candidates[0] == {
        "type": installment_template_1.type.value,
        "amount": 10050,
        "account_number": installment_template_1.account_number,
        "due_date": "2022-01-10",
    }

    assert installment_candidates[1] == {
        "type": installment_template_2.type.value,
        "amount": 1234568,  # 10% of 123456,78e in cents
        "account_number": installment_template_2.account_number,
        "due_date": None,
    }

    assert installment_candidates[2] == {
        "type": installment_template_3.type.value,
        "amount": 69136,  # 0,7% of 987654,43e in cents
        "account_number": installment_template_3.account_number,
        "due_date": None,
    }

    assert installment_candidates[3] == {
        "type": installment_template_4.type.value,
        "amount": 1703704,  # 17,25% of 987654,43e in cents
        "account_number": installment_template_4.account_number,
        "due_date": None,
    }


@pytest.mark.parametrize("ownership_type", ("HASO", "Hitas"))
@pytest.mark.django_db
def test_contract_pdf_creation(profile_api_client, ownership_type):
    apartment = ApartmentDocumentFactory(project_ownership_type=ownership_type)
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    response = profile_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-contract",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"

    test_value = (
        apartment.project_contract_right_of_occupancy_payment_verification
        if ownership_type == "HASO"
        else apartment.project_realty_id
    )
    assert bytes(test_value, encoding="utf-8") in response.content


@pytest.mark.parametrize("comment", ("Foo", ""))
@pytest.mark.django_db
def test_apartment_reservation_set_state(user_api_client, comment):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"state": "reserved", "comment": comment}
    response = user_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-set-state",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert len(response.data.keys()) == 3
    assert response.data.pop("timestamp")
    assert response.data == {
        "state": "reserved",
        "comment": comment,
    }

    assert reservation.state_change_events.count() == 2
    state_change_event = reservation.state_change_events.last()
    assert state_change_event.timestamp
    assert state_change_event.state == ApartmentReservationState.RESERVED
    assert state_change_event.comment == comment
    assert state_change_event.user == user_api_client.user


@pytest.mark.parametrize("ownership_type", ("Haso", "Puolihitas", "Hitas"))
@pytest.mark.django_db
def test_apartment_reservation_canceling(user_api_client, ownership_type):
    apartment = ApartmentDocumentFactory(project_ownership_type=ownership_type)
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"cancellation_reason": "terminated", "comment": "Foo"}
    response = user_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert len(response.data.keys()) == 4
    assert response.data.pop("timestamp")
    assert response.data == {
        "state": "canceled",
        "comment": "Foo",
        "cancellation_reason": "terminated",
    }

    assert reservation.state_change_events.count() == 2
    state_change_event = reservation.state_change_events.last()
    assert state_change_event.timestamp
    assert state_change_event.state == ApartmentReservationState.CANCELED
    assert state_change_event.cancellation_reason
    assert state_change_event.user == user_api_client.user


@pytest.mark.django_db
def test_apartment_reservation_cancellation_reason_validation(user_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"comment": "Foo"}
    response = user_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert "cancellation_reason" in str(response.data)
