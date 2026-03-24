import pytest

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation
from application_form.tests.factories import ApartmentReservationFactory
from customer.tests.factories import CustomerFactory


def _queue_preview_url(apartment_uuid):
    return f"/v1/sales/apartments/{apartment_uuid}/queue/preview/"


def _active_positions_from_response(response_data):
    active = [item for item in response_data if item["queue_position"] is not None]
    return sorted(item["queue_position"] for item in active)


@pytest.mark.django_db
def test_queue_preview_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.SUBMITTED,
    )

    response = user_api_client.post(
        _queue_preview_url(apartment.uuid),
        data={
            "reservation_id": reservation.id,
            "queue_position": 1,
            "state": ApartmentReservationState.SUBMITTED.value,
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_queue_preview_reorders_queue_on_position_change(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    reservation_1 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, queue_position=1, list_position=1
    )
    reservation_2 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, queue_position=2, list_position=2
    )
    reservation_3 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, queue_position=3, list_position=3
    )
    reservation_4 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, queue_position=4, list_position=4
    )
    old_positions = {
        reservation_1.id: reservation_1.queue_position,
        reservation_2.id: reservation_2.queue_position,
        reservation_3.id: reservation_3.queue_position,
        reservation_4.id: reservation_4.queue_position,
    }

    response = sales_ui_salesperson_api_client.post(
        _queue_preview_url(apartment.uuid),
        data={
            "reservation_id": reservation_3.id,
            "queue_position": 1,
            "state": ApartmentReservationState.SUBMITTED.value,
        },
        format="json",
    )

    assert response.status_code == 200
    response_by_id = {item["id"]: item for item in response.data if item["id"] is not None}
    assert _active_positions_from_response(response.data) == [1, 2, 3, 4]
    assert response_by_id[reservation_3.id]["queue_position"] == 1

    # Preview must not persist any queue changes.
    for reservation in [reservation_1, reservation_2, reservation_3, reservation_4]:
        reservation.refresh_from_db()
        assert reservation.queue_position == old_positions[reservation.id]


@pytest.mark.django_db
def test_queue_preview_reorders_queue_when_submitted_late_toggled(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory(project_ownership_type="HASO")
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=1,
        list_position=1,
        submitted_late=False,
        right_of_residence=100,
        right_of_residence_is_old_batch=True,
        state=ApartmentReservationState.SUBMITTED,
    )
    reservation_2 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=2,
        list_position=2,
        submitted_late=True,
        right_of_residence=50,
        right_of_residence_is_old_batch=True,
        state=ApartmentReservationState.SUBMITTED,
    )
    target_reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=3,
        list_position=3,
        submitted_late=False,
        right_of_residence=10,
        right_of_residence_is_old_batch=True,
        state=ApartmentReservationState.SUBMITTED,
    )

    response = sales_ui_salesperson_api_client.post(
        _queue_preview_url(apartment.uuid),
        data={
            "reservation_id": target_reservation.id,
            "submitted_late": True,
            "state": ApartmentReservationState.SUBMITTED.value,
        },
        format="json",
    )

    assert response.status_code == 200
    response_by_id = {item["id"]: item for item in response.data if item["id"] is not None}
    assert response_by_id[target_reservation.id]["submitted_late"] is True
    assert response_by_id[target_reservation.id]["queue_position"] == 2
    assert response_by_id[reservation_2.id]["queue_position"] == 3
    assert _active_positions_from_response(response.data) == [1, 2, 3]

    # Preview must not persist submitted_late or queue changes.
    target_reservation.refresh_from_db()
    reservation_2.refresh_from_db()
    assert target_reservation.submitted_late is False
    assert target_reservation.queue_position == 3
    assert reservation_2.queue_position == 2


@pytest.mark.django_db
def test_queue_preview_adds_new_reservation_at_requested_position(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, queue_position=1, list_position=1
    )
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, queue_position=2, list_position=2
    )
    new_customer = CustomerFactory()

    initial_count = ApartmentReservation.objects.filter(apartment_uuid=apartment.uuid).count()
    response = sales_ui_salesperson_api_client.post(
        _queue_preview_url(apartment.uuid),
        data={
            "customer_id": new_customer.id,
            "queue_position": 1,
            "submitted_late": True,
            "state": ApartmentReservationState.SUBMITTED.value,
        },
        format="json",
    )

    assert response.status_code == 200
    response_by_customer = {
        item["customer"]["id"]: item for item in response.data if item.get("customer")
    }
    assert _active_positions_from_response(response.data) == [1, 2, 3]
    assert response_by_customer[new_customer.id]["queue_position"] == 1

    # Preview must not create a persisted reservation row.
    assert (
        ApartmentReservation.objects.filter(apartment_uuid=apartment.uuid).count()
        == initial_count
    )


@pytest.mark.django_db
def test_queue_preview_keeps_canceled_reservations_out_of_active_positions(
    sales_ui_salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=None,
        list_position=1,
        state=ApartmentReservationState.CANCELED,
    )
    reservation_1 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=1,
        list_position=2,
        state=ApartmentReservationState.SUBMITTED,
    )
    reservation_2 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        queue_position=2,
        list_position=3,
        state=ApartmentReservationState.SUBMITTED,
    )

    response = sales_ui_salesperson_api_client.post(
        _queue_preview_url(apartment.uuid),
        data={
            "reservation_id": reservation_2.id,
            "queue_position": 1,
            "state": ApartmentReservationState.SUBMITTED.value,
        },
        format="json",
    )

    assert response.status_code == 200
    canceled_items = [item for item in response.data if item["state"] == "canceled"]
    assert len(canceled_items) == 1
    assert canceled_items[0]["queue_position"] is None
    assert _active_positions_from_response(response.data) == [1, 2]

    # Preview must not persist active queue changes.
    reservation_1.refresh_from_db()
    reservation_2.refresh_from_db()
    assert reservation_1.queue_position == 1
    assert reservation_2.queue_position == 2
