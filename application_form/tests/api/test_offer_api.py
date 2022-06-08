import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    OfferState,
)
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
)
from application_form.tests.factories import ApartmentReservationFactory, OfferFactory
from customer.tests.factories import CustomerFactory


@pytest.mark.django_db
def test_create_offer_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    week_in_future = timezone.localdate() + timedelta(days=7)

    data = {
        "apartment_reservation_id": reservation.id,
        "valid_until": week_in_future,
        "comment": "Foobar.",
    }

    response = user_api_client.post(
        reverse(
            "application_form:sales-offer-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_offer(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    week_in_future = timezone.localdate() + timedelta(days=7)

    data = {
        "apartment_reservation_id": reservation.id,
        "valid_until": week_in_future,
        "comment": "Foobar.",
    }

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-offer-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 201, response.data

    assert response.data.pop("created_at")
    assert response.data.pop("id")
    assert response.data == {
        "apartment_reservation_id": reservation.id,
        "comment": "Foobar.",
        "valid_until": str(week_in_future),
        "state": "pending",
        "concluded_at": None,
        "is_expired": False,
    }

    offer = reservation.offer
    assert offer.apartment_reservation == reservation
    assert offer.comment == "Foobar."
    assert offer.valid_until == week_in_future
    assert offer.state == OfferState.PENDING
    assert offer.concluded_at is None


@pytest.mark.django_db
def test_create_offer_already_exists(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    week_in_future = timezone.localdate() + timedelta(days=7)

    data = {
        "apartment_reservation_id": reservation.id,
        "valid_until": week_in_future,
        "comment": "Foobar.",
    }

    OfferFactory(
        apartment_reservation=reservation,
        state=OfferState.PENDING,
        concluded_at=timezone.now(),
    )

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-offer-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 400
    assert "already" in str(response.data)


@pytest.mark.django_db
def test_update_offer_unauthorized(user_api_client):
    today = timezone.localdate()
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    offer = OfferFactory(
        apartment_reservation=reservation,
        valid_until=today + timedelta(days=1),
        comment="old comment",
    )

    data = {
        "valid_until": str(today + timedelta(days=2)),
        "comment": "new comment",
    }

    response = user_api_client.patch(
        reverse(
            "application_form:sales-offer-detail",
            kwargs={"pk": offer.pk},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_update_offer(salesperson_api_client):
    today = timezone.localdate()
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    offer = OfferFactory(
        apartment_reservation=reservation,
        valid_until=today + timedelta(days=1),
        comment="old comment",
    )

    data = {
        "valid_until": str(today + timedelta(days=2)),
        "comment": "new comment",
    }

    response = salesperson_api_client.patch(
        reverse(
            "application_form:sales-offer-detail",
            kwargs={"pk": offer.pk},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert response.data.pop("created_at")
    assert response.data == {
        "id": offer.id,
        "apartment_reservation_id": reservation.id,
        "valid_until": str(today + timedelta(days=2)),
        "state": "pending",
        "concluded_at": None,
        "comment": "new comment",
        "is_expired": False,
    }

    offer.refresh_from_db()
    assert offer.valid_until == today + timedelta(days=2)
    assert offer.state == OfferState.PENDING
    assert offer.concluded_at is None
    assert offer.comment == "new comment"


@pytest.mark.parametrize("new_state", ("accepted", "rejected"))
@pytest.mark.django_db
def test_update_offer_change_state(salesperson_api_client, new_state):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.OFFERED
    )
    offer = OfferFactory(
        apartment_reservation=reservation,
        valid_until=timezone.localdate() + timedelta(days=1),
    )

    data = {"state": new_state}

    response = salesperson_api_client.patch(
        reverse(
            "application_form:sales-offer-detail",
            kwargs={"pk": offer.pk},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert response.data["state"] == new_state
    assert response.data["concluded_at"]

    offer.refresh_from_db()
    reservation.refresh_from_db()
    if new_state == "accepted":
        assert offer.state == OfferState.ACCEPTED
        assert reservation.state == ApartmentReservationState.OFFER_ACCEPTED
    else:
        assert offer.state == OfferState.REJECTED
        assert reservation.state == ApartmentReservationState.CANCELED
    assert offer.concluded_at


@pytest.mark.parametrize("state", ("accepted", "rejected"))
@pytest.mark.django_db
def test_cannot_update_concluded_offer_valid_until_or_state(
    salesperson_api_client, state
):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    offer = OfferFactory(
        apartment_reservation=reservation,
        valid_until=timezone.localdate() + timedelta(days=1),
        state=state,
    )

    for data in (
        {
            "valid_until": "2040-01-01",
        },
        {
            "state": "accepted" if state == "rejected" else "rejected",
        },
    ):
        response = salesperson_api_client.patch(
            reverse(
                "application_form:sales-offer-detail",
                kwargs={"pk": offer.pk},
            ),
            data=data,
            format="json",
        )
        assert response.status_code == 400
        assert "Only comment can be edited" in str(response.data)


@pytest.mark.parametrize("state", ("accepted", "rejected"))
@pytest.mark.django_db
def test_update_concluded_offer_comment(salesperson_api_client, state):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    offer = OfferFactory(
        apartment_reservation=reservation,
        valid_until=timezone.localdate() + timedelta(days=1),
        state=state,
        comment="old comment",
    )

    data = {"comment": "new comment"}

    response = salesperson_api_client.patch(
        reverse(
            "application_form:sales-offer-detail",
            kwargs={"pk": offer.pk},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert response.data["comment"] == "new comment"
    offer.refresh_from_db()
    assert offer.comment == "new comment"


@pytest.mark.django_db
def test_update_offer_change_to_expired(salesperson_api_client):
    today = timezone.localdate()
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.OFFERED
    )
    offer = OfferFactory(
        apartment_reservation=reservation,
        state=OfferState.PENDING,
        valid_until=today,
    )

    data = {"valid_until": str(today - timedelta(days=1))}

    response = salesperson_api_client.patch(
        reverse(
            "application_form:sales-offer-detail",
            kwargs={"pk": offer.pk},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200
    assert response.data["is_expired"] is True

    reservation.refresh_from_db()
    assert reservation.state == ApartmentReservationState.OFFER_EXPIRED


@pytest.mark.django_db
def test_create_offer_cancel_other_reservations(salesperson_api_client):
    apartment_1 = ApartmentDocumentFactory()
    apartment_2 = ApartmentDocumentFactory(project_uuid=apartment_1.project_uuid)
    apartment_3 = ApartmentDocumentFactory(project_uuid=apartment_1.project_uuid)
    customer = CustomerFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment_1.uuid,
        state=ApartmentReservationState.SUBMITTED,
        list_position=1,
        customer=customer,
    )
    ApartmentReservationFactory(
        apartment_uuid=apartment_2.uuid,
        state=ApartmentReservationState.CANCELED,
        list_position=1,
        customer=customer,
    )
    other_reservation = ApartmentReservationFactory(
        apartment_uuid=apartment_3.uuid,
        list_position=1,
        customer=customer,
        state=ApartmentReservationState.SUBMITTED,
    )
    week_in_future = timezone.localdate() + timedelta(days=7)

    data = {
        "apartment_reservation_id": reservation.id,
        "valid_until": week_in_future,
        "comment": "Foobar.",
    }

    assert (
        ApartmentReservation.objects.filter(
            customer=customer, state=ApartmentReservationState.CANCELED
        ).count()
        == 1
    )

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-offer-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 201, response.data
    reservation.refresh_from_db()
    assert reservation.state == ApartmentReservationState.OFFERED
    assert (
        ApartmentReservation.objects.filter(
            customer=customer, state=ApartmentReservationState.CANCELED
        ).count()
        == 2
    )
    state_change_event = ApartmentReservationStateChangeEvent.objects.filter(
        reservation=other_reservation, state=ApartmentReservationState.CANCELED
    )
    assert state_change_event.count() == 1
    assert (
        state_change_event[0].cancellation_reason
        == ApartmentReservationCancellationReason.OTHER_APARTMENT_OFFERED
    )
    assert apartment_1.apartment_number in state_change_event[0].comment
