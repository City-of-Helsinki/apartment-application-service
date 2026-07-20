from datetime import timedelta
from uuid import uuid4

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
    create_apartment=True,
    primary_email=None,
):
    """
    Create a pending offer fixture.

    Parameters:
        valid_until: Offer validity date.
        reservation_state: Reservation state (default OFFERED).
        message_sent_at: Optional already-sent timestamp.
        offer_state: Offer state (default PENDING).
        secondary_profile: Optional co-applicant profile.
        create_apartment: When False, reservation uses an unindexed UUID.
        primary_email: Override primary profile email (use "" for none).

    Returns:
        Tuple of (offer, apartment_or_None, profile, reservation).
    """
    apartment = ApartmentDocumentFactory() if create_apartment else None
    apartment_uuid = apartment.uuid if apartment is not None else uuid4()
    profile_kwargs = {}
    if primary_email is not None:
        profile_kwargs["email"] = primary_email
    profile = ProfileFactory(**profile_kwargs)
    customer = CustomerFactory(
        primary_profile=profile,
        secondary_profile=secondary_profile,
    )
    application = ApplicationFactory(customer=customer)
    application_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment_uuid,
        application=application,
        priority_number=1,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
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
    - Claims returned offers by setting message_sent_at.
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
    offer.refresh_from_db()
    assert offer.message_sent_at is not None


@pytest.mark.django_db
def test_pending_messages_claims_offer_so_second_fetch_is_empty(
    drupal_server_api_client,
):
    """
    - First fetch claims the offer (sets message_sent_at).
    - Second fetch does not return the same offer (prevents duplicate emails).
    """
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(valid_until=today + timedelta(days=7))

    first = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )
    second = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert first.status_code == 200
    assert len(first.data) == 1
    assert first.data[0]["id"] == offer.id
    assert second.status_code == 200
    assert second.data == []
    offer.refresh_from_db()
    assert offer.message_sent_at is not None


@pytest.mark.django_db
def test_pending_messages_excludes_expired_offers(drupal_server_api_client):
    """
    - Excludes offers whose valid_until is in the past.
    - Does not claim expired offers.
    """
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(valid_until=today - timedelta(days=1))

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert response.status_code == 200
    assert len(response.data) == 0
    offer.refresh_from_db()
    assert offer.message_sent_at is None


@pytest.mark.django_db
def test_pending_messages_marks_offers_without_recipients(
    drupal_server_api_client,
):
    """
    - Offers with no recipient emails are not returned.
    - Those offers are marked message_sent_at so cron does not retry forever.
    """
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(
        valid_until=today + timedelta(days=7),
        primary_email="",
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert response.status_code == 200
    assert len(response.data) == 0
    offer.refresh_from_db()
    assert offer.message_sent_at is not None


@pytest.mark.django_db
def test_pending_messages_skips_missing_apartment_without_marking(
    drupal_server_api_client,
):
    """
    - Offers whose apartment is missing from the search index are omitted.
    - message_sent_at stays null so delivery can retry after indexing.
    """
    today = timezone.localdate()
    offer, _, _, _ = _create_pending_offer(
        valid_until=today + timedelta(days=7),
        create_apartment=False,
    )

    response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert response.status_code == 200
    assert len(response.data) == 0
    offer.refresh_from_db()
    assert offer.message_sent_at is None


@pytest.mark.django_db
def test_pending_messages_includes_offer_after_apartment_indexed(
    drupal_server_api_client,
):
    """
    - After a missing apartment is added to the index, the offer is returned.
    """
    today = timezone.localdate()
    offer, _, _, reservation = _create_pending_offer(
        valid_until=today + timedelta(days=7),
        create_apartment=False,
    )

    first = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )
    assert first.status_code == 200
    assert len(first.data) == 0

    apartment = ApartmentDocumentFactory(uuid=reservation.apartment_uuid)
    second = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert second.status_code == 200
    assert len(second.data) == 1
    assert second.data[0]["id"] == offer.id
    assert str(second.data[0]["project_uuid"]) == str(apartment.project_uuid)


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
