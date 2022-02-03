import pytest
from django.urls import reverse

from application_form.tests.factories import ApartmentReservationFactory
from invoicing.tests.factories import ApartmentInstallmentFactory


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
        "apartment_uuid": reservation.apartment_uuid,
        "queue_position": reservation.queue_position,
        "state": reservation.state.value,
        "lottery_position": None,
    }
