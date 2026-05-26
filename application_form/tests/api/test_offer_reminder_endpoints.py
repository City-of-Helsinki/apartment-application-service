from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import ApartmentReservationState, OfferState
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    OfferFactory,
)
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory


def _create_pending_offer(
    valid_until,
    reservation_state=ApartmentReservationState.OFFERED,
    reminder_sent_at=None,
    offer_state=OfferState.PENDING,
):
    apartment = ApartmentDocumentFactory()
    profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile)
    application = ApplicationFactory(customer=customer)
    application_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=application,
        priority_number=1,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        application_apartment=application_apartment,
        customer=customer,
        state=reservation_state,
    )
    offer = OfferFactory(
        apartment_reservation=reservation,
        state=offer_state,
        valid_until=valid_until,
        reminder_sent_at=reminder_sent_at,
    )
    return offer, apartment, profile


@pytest.mark.django_db
def test_pending_reminders_returns_due_offers(drupal_server_api_client):
    """
    - Returns only pending, unreminded offers due within days_before.
    """
    today = timezone.localdate()
    due_offer, apartment, profile = _create_pending_offer(
        valid_until=today + timedelta(days=1)
    )
    _create_pending_offer(valid_until=today + timedelta(days=10))
    _create_pending_offer(
        valid_until=today + timedelta(days=1),
        reminder_sent_at=timezone.now(),
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_reminders"),
        {"days_before": 1},
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    item = response.data[0]
    assert item["id"] == due_offer.id
    assert item["valid_until"] == str(today + timedelta(days=1))
    assert str(item["apartment_uuid"]) == str(apartment.uuid)
    assert str(item["project_uuid"]) == str(apartment.project_uuid)
    assert item["customer"]["primary_profile"]["email"] == profile.email


@pytest.mark.django_db
def test_pending_reminders_excludes_past_deadline(drupal_server_api_client):
    """
    - Excludes offers with valid_until in the past.
    """
    today = timezone.localdate()
    _create_pending_offer(valid_until=today - timedelta(days=1))

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_reminders"),
        {"days_before": 1},
    )

    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_pending_reminders_excludes_non_offered_reservation(
    drupal_server_api_client,
):
    """
    - Excludes offers where reservation state has moved on.
    """
    today = timezone.localdate()
    _create_pending_offer(
        valid_until=today + timedelta(days=1),
        reservation_state=ApartmentReservationState.CANCELED,
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_reminders"),
        {"days_before": 1},
    )

    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_pending_reminders_unauthorized(api_client, profile_api_client):
    """
    - Reminder list requires Drupal server token.
    """
    response = api_client.get(reverse("application_form:pending_offer_reminders"))
    assert response.status_code in (401, 403)

    response = profile_api_client.get(
        reverse("application_form:pending_offer_reminders")
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_mark_reminder_sent(drupal_server_api_client):
    """
    - mark_reminder_sent sets reminder_sent_at on pending offer.
    """
    today = timezone.localdate()
    offer, _, _ = _create_pending_offer(valid_until=today + timedelta(days=1))
    assert offer.reminder_sent_at is None

    response = drupal_server_api_client.post(
        reverse(
            "application_form:mark_offer_reminder_sent",
            kwargs={"offer_id": offer.pk},
        ),
    )

    assert response.status_code == 200
    assert response.data["reminder_sent_at"] is not None
    offer.refresh_from_db()
    assert offer.reminder_sent_at is not None


@pytest.mark.django_db
def test_mark_reminder_sent_idempotent(drupal_server_api_client):
    """
    - mark_reminder_sent is idempotent when already set.
    """
    sent_at = timezone.now() - timedelta(hours=2)
    today = timezone.localdate()
    offer, _, _ = _create_pending_offer(
        valid_until=today + timedelta(days=1),
        reminder_sent_at=sent_at,
    )

    response = drupal_server_api_client.post(
        reverse(
            "application_form:mark_offer_reminder_sent",
            kwargs={"offer_id": offer.pk},
        ),
    )

    assert response.status_code == 200
    offer.refresh_from_db()
    assert offer.reminder_sent_at == sent_at


@pytest.mark.django_db
def test_mark_reminder_sent_unauthorized(api_client):
    """
    - mark_reminder_sent requires Drupal server token.
    """
    today = timezone.localdate()
    offer, _, _ = _create_pending_offer(valid_until=today + timedelta(days=1))

    response = api_client.post(
        reverse(
            "application_form:mark_offer_reminder_sent",
            kwargs={"offer_id": offer.pk},
        ),
    )

    assert response.status_code in (401, 403)
