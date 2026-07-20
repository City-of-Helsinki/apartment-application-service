from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apartment.services import get_offer_message_subject_and_body
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
    message_sent_at=None,
    offer_state=OfferState.PENDING,
    secondary_profile=None,
):
    apartment = ApartmentDocumentFactory()
    profile = ProfileFactory()
    customer = CustomerFactory(
        primary_profile=profile,
        secondary_profile=secondary_profile,
    )
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
        message_sent_at=message_sent_at,
    )
    return offer, apartment, profile, reservation


@pytest.mark.django_db
def test_pending_messages_returns_unsent_offers(drupal_server_api_client):
    """
    - Returns pending offers with message_sent_at unset and OFFERED reservation.
    - Includes subject, body, recipients, and project_uuid.
    """
    today = timezone.localdate()
    secondary = ProfileFactory()
    offer, apartment, profile, reservation = _create_pending_offer(
        valid_until=today + timedelta(days=7),
        secondary_profile=secondary,
    )
    _create_pending_offer(
        valid_until=today + timedelta(days=7),
        message_sent_at=timezone.now(),
    )
    _create_pending_offer(
        valid_until=today + timedelta(days=7),
        offer_state=OfferState.ACCEPTED,
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    item = response.data[0]
    assert item["id"] == offer.id
    assert item["valid_until"] == str(today + timedelta(days=7))
    assert str(item["project_uuid"]) == str(apartment.project_uuid)
    expected_subject, expected_body = get_offer_message_subject_and_body(
        reservation,
        valid_until=offer.valid_until,
    )
    assert item["subject"] == expected_subject
    assert item["body"] == expected_body
    recipient_emails = {r["email"] for r in item["recipients"]}
    assert profile.email in recipient_emails
    assert secondary.email in recipient_emails


@pytest.mark.django_db
def test_pending_messages_excludes_non_offered_reservation(
    drupal_server_api_client,
):
    """
    - Excludes offers where reservation state is not OFFERED.
    """
    today = timezone.localdate()
    _create_pending_offer(
        valid_until=today + timedelta(days=7),
        reservation_state=ApartmentReservationState.CANCELED,
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_pending_messages_excludes_non_pending_offers(drupal_server_api_client):
    """
    - Excludes accepted or rejected offers.
    """
    today = timezone.localdate()
    _create_pending_offer(
        valid_until=today + timedelta(days=7),
        offer_state=OfferState.REJECTED,
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_pending_messages_unauthorized(api_client, profile_api_client):
    """
    - Pending messages list requires Drupal server token.
    """
    response = api_client.get(reverse("application_form:pending_offer_messages"))
    assert response.status_code in (401, 403)

    response = profile_api_client.get(
        reverse("application_form:pending_offer_messages")
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_mark_message_sent(drupal_server_api_client):
    """
    - mark_message_sent sets message_sent_at on pending offer.
    """
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(valid_until=today + timedelta(days=7))
    assert offer.message_sent_at is None

    response = drupal_server_api_client.post(
        reverse(
            "application_form:mark_offer_message_sent",
            kwargs={"offer_id": offer.pk},
        ),
    )

    assert response.status_code == 200
    assert response.data["message_sent_at"] is not None
    offer.refresh_from_db()
    assert offer.message_sent_at is not None


@pytest.mark.django_db
def test_mark_message_sent_idempotent(drupal_server_api_client):
    """
    - mark_message_sent is idempotent when already set.
    """
    sent_at = timezone.now() - timedelta(hours=2)
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(
        valid_until=today + timedelta(days=7),
        message_sent_at=sent_at,
    )

    response = drupal_server_api_client.post(
        reverse(
            "application_form:mark_offer_message_sent",
            kwargs={"offer_id": offer.pk},
        ),
    )

    assert response.status_code == 200
    offer.refresh_from_db()
    assert offer.message_sent_at == sent_at


@pytest.mark.django_db
def test_mark_message_sent_unauthorized(api_client):
    """
    - mark_message_sent requires Drupal server token.
    """
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(valid_until=today + timedelta(days=7))

    response = api_client.post(
        reverse(
            "application_form:mark_offer_message_sent",
            kwargs={"offer_id": offer.pk},
        ),
    )

    assert response.status_code in (401, 403)
