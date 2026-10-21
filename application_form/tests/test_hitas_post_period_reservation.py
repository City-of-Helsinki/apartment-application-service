"""
Tests for HITAS post-application-period reservations ("tee varaus").

After the application period has ended, a customer can make a reservation on a
free HITAS apartment when `project_can_apply_afterwards` is True. The rules are:
- Only one apartment per reservation (single apartment enforced)
- Apartment must be FREE_FOR_RESERVATIONS
- Successful reservation is marked RESERVED and then OFFERED (apartment is no
  longer free)
- An offer valid for DEFAULT_OFFER_VALID_DAYS is created for the customer and
  delivered through the same Drupal pending-offer flow as other offers
- Customer may not already have an active reservation in the project
- Sales notification email is sent to the project salesperson and the general
  sales mailbox on successful reservation
- HASO late-apply path is unchanged

Tests:
- Positive: HITAS free apartment after period with can_apply_afterwards
- Positive: reservation is RESERVED then OFFERED, apartment is OFFERED
- Positive: offer is created and exposed via pending_offer_messages
- Positive: sales API late HITAS application creates an offer with handler
- Positive: Drupal apartment_states reports RESERVED
- Positive: sales UI project-detail reports offered
- Negative: no offer for HASO late, HITAS in-period, or rejected applications
- Email: HITAS goes to salesperson and sales mailbox, HASO only to salesperson
- Reject: apartment already has a reserved reservation in Django
- Reject: second customer cannot reserve the same apartment
- Reject: period not ended (normal HITAS apply still works, stays SUBMITTED)
- Reject: can_apply_afterwards is False for HITAS
- Reject: more than one apartment submitted
- Reject: customer already has an active reservation in the project
- Reject: apartment is sold / reserved / reserved_haso / missing state
- Reject: sales-created reservation without application_apartment
- Reject: get_apartment raises ObjectDoesNotExist
- Allow: prior canceled reservation does not block
- Email: salesperson notification sent on success
- HASO late apply unchanged (still cancels prior, new stays SUBMITTED)
"""

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.test import override_settings, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from apartment.enums import ApartmentState, OwnershipType
from apartment.tests.factories import add_to_store, ApartmentDocumentFactory
from apartment.utils import get_apartment_state_from_apartment_uuid
from application_form.enums import (
    ApartmentReservationState,
    ApplicationType,
    OfferState,
)
from application_form.models import ApartmentReservation, Application, Offer
from application_form.services.application import get_sales_notification_recipients
from application_form.services.constants import DEFAULT_OFFER_VALID_DAYS
from application_form.tests.conftest import create_application_data, generate_apartments
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from application_form.tests.utils import (
    make_late_haso_apartment,
    post_single_apartment_application,
)
from connections.enums import ApartmentStateOfSale
from customer.tests.factories import CustomerFactory
from users.enums import Roles
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token

SALES_MAILBOX = "sales@example.com"
AGENT_EMAIL = "agent@example.com"


def _detail_message(response):
    """
    Return the human-readable detail message from an API error response.

    Parameters:
        response: DRF response with custom exception handler formatting.

    Returns:
        str: Detail error message.
    """
    detail = response.data["detail"]
    if isinstance(detail, dict):
        return str(detail["message"])
    return str(detail)


def _make_hitas_free_apartment_after_period(**kwargs):
    """
    Create a single HITAS apartment past its application period that is
    free for reservations.

    Parameters:
        **kwargs: Overrides for ApartmentDocumentFactory fields.

    Returns:
        ApartmentDocument: The created apartment document.
    """
    defaults = {
        "project_ownership_type": OwnershipType.HITAS.value,
        "project_can_apply_afterwards": True,
        "project_application_end_time": (
            datetime.now().replace(tzinfo=timezone.get_default_timezone())
            - timedelta(days=1)
        ),
        "apartment_state_of_sale": ApartmentStateOfSale.FREE_FOR_RESERVATIONS.value,
    }
    defaults.update(kwargs)
    apt = ApartmentDocumentFactory(**defaults)
    add_to_store([apt])
    return apt


def _post_hitas_reservation(api_client, profile, apartment):
    """
    POST a single-apartment HITAS application for the given profile.

    Parameters:
        api_client: DRF API client.
        profile: Profile of the applicant.
        apartment: Apartment document to reserve.

    Returns:
        tuple: (response, request_data) from the applications endpoint.
    """
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]
    return (
        api_client.post(
            reverse("application_form:application-list"), data, format="json"
        ),
        data,
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_succeeds(api_client, elasticsearch):
    """
    A customer can reserve a free HITAS apartment after the application period when
    project_can_apply_afterwards is True.

    - POST /v1/applications/ returns 201
    - ApartmentReservation is reserved first and then offered
    - Apartment derived state is offered
    - Application is marked submitted_late
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()

    with patch(
        "application_form.api.serializers.send_sales_notification_email"
    ) as mock_email:
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, data = _post_hitas_reservation(api_client, profile, apartment)
        mock_email.assert_called_once()

    assert response.status_code == 201
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert application.submitted_late is True
    reservation = ApartmentReservation.objects.get(
        apartment_uuid=apartment.uuid,
        application_apartment__application=application,
    )
    assert reservation.state == ApartmentReservationState.OFFERED
    event_states = list(
        reservation.state_change_events.order_by("timestamp", "id").values_list(
            "state", flat=True
        )
    )
    assert event_states[-2:] == [
        ApartmentReservationState.RESERVED,
        ApartmentReservationState.OFFERED,
    ]
    assert (
        get_apartment_state_from_apartment_uuid(apartment.uuid)
        == ApartmentState.OFFERED.value
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_salesperson_email_sent(
    api_client, elasticsearch
):
    """
    A salesperson notification email is sent when a HITAS post-period reservation
    is created.

    - send_sales_notification_email is called with the new application
    """
    apartment = _make_hitas_free_apartment_after_period(
        project_estate_agent_email="agent@example.com"
    )
    profile = ProfileFactory()

    with patch(
        "application_form.api.serializers.send_sales_notification_email"
    ) as mock_email:
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, data = _post_hitas_reservation(api_client, profile, apartment)
        assert mock_email.call_count == 1
        call_args = mock_email.call_args

    assert response.status_code == 201
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert call_args[0][0] == application


@pytest.mark.django_db
def test_hitas_post_period_reservation_marks_apartment_reserved_for_drupal(
    api_client, drupal_server_api_client, elasticsearch
):
    """
    After a HITAS post-period reservation, Drupal apartment_states reports RESERVED.

    - POST /v1/applications/ returns 201
    - GET /v1/sales/apartment_states/ returns RESERVED for the apartment
    """
    apartment = _make_hitas_free_apartment_after_period()
    LotteryEventFactory(apartment_uuid=apartment.uuid)
    profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201

    states_response = drupal_server_api_client.get(
        reverse("application_form:apartment_states")
    )
    assert states_response.status_code == 200
    assert states_response.data[str(apartment.uuid)] == ApartmentStateOfSale.RESERVED


@pytest.mark.django_db
def test_hitas_post_period_reservation_sales_ui_reports_reserved(
    api_client, sales_ui_salesperson_api_client, elasticsearch
):
    """
    After a HITAS post-period reservation, the salesperson project-detail
    API reports the apartment as offered.

    - POST /v1/applications/ returns 201
    - GET project-detail apartment.state is offered
    - reserved_apartment_count is 1
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201

    detail = sales_ui_salesperson_api_client.get(
        reverse(
            "apartment:project-detail",
            kwargs={"project_uuid": apartment.project_uuid},
        ),
        format="json",
    )
    assert detail.status_code == 200
    apartment_data = next(
        item
        for item in detail.data["apartments"]
        if item["apartment_uuid"] == str(apartment.uuid)
    )
    assert apartment_data["state"] == ApartmentState.OFFERED.value
    assert detail.data["reserved_apartment_count"] == 1
    assert detail.data["free_apartment_count"] == 0


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_db_already_reserved(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when Django already has a
    reserved reservation, even if Elasticsearch still says the apartment is
    free.

    - POST returns 400 with the not-free detail message
    - Existing reserved reservation is unchanged
    """
    apartment = _make_hitas_free_apartment_after_period()
    existing = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
        queue_position=1,
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Cannot reserve an apartment that is not free"
    )
    existing.refresh_from_db()
    assert existing.state == ApartmentReservationState.RESERVED
    assert (
        ApartmentReservation.objects.filter(apartment_uuid=apartment.uuid).count() == 1
    )


@pytest.mark.django_db
def test_hitas_post_period_second_customer_reservation_rejected(
    api_client, elasticsearch
):
    """
    After a successful HITAS post-period reservation, another customer cannot
    reserve the same apartment while Elasticsearch still reports it as free.

    - First POST returns 201
    - Second POST from a different profile returns 400
    """
    apartment = _make_hitas_free_apartment_after_period()
    first_profile = ProfileFactory()
    second_profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            first_response, _ = _post_hitas_reservation(
                api_client, first_profile, apartment
            )

    assert first_response.status_code == 201

    second_response, _ = _post_hitas_reservation(api_client, second_profile, apartment)

    assert second_response.status_code == 400
    assert _detail_message(second_response) == gettext(
        "Cannot reserve an apartment that is not free"
    )
    assert (
        ApartmentReservation.objects.filter(apartment_uuid=apartment.uuid).count() == 1
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_can_apply_afterwards_false(
    api_client, elasticsearch
):
    """
    A HITAS late application is rejected when project_can_apply_afterwards is False.

    - POST returns 400 with the late-application detail message
    """
    apartment = _make_hitas_free_apartment_after_period(
        project_can_apply_afterwards=False
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Cannot submit late application to this apartment"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_with_multiple_apartments(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation with more than one apartment is rejected.

    - POST returns 400 with the single-apartment detail message
    """
    apartments = generate_apartments(
        elasticsearch,
        2,
        {
            "project_ownership_type": OwnershipType.HITAS.value,
            "project_can_apply_afterwards": True,
            "project_application_end_time": (
                datetime.now().replace(tzinfo=timezone.get_default_timezone())
                - timedelta(days=1)
            ),
            "apartment_state_of_sale": ApartmentStateOfSale.FREE_FOR_RESERVATIONS.value,
        },
    )
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=apartments,
    )
    data["apartments"] = [
        {"priority": 0, "identifier": str(apartments[0].uuid)},
        {"priority": 1, "identifier": str(apartments[1].uuid)},
    ]

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "HITAS post-period reservation must contain exactly one apartment"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_customer_already_has_reservation(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when the customer already has an
    active reservation in the same project.

    - POST returns 400 with the duplicate-reservation detail message
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile)
    existing_app_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=ApplicationFactory(customer=customer, type=ApplicationType.HITAS),
    )
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        state=ApartmentReservationState.SUBMITTED,
        application_apartment=existing_app_apartment,
    )

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Customer already has a reservation in this project"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_for_sold_apartment(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when the target apartment is sold.

    - POST returns 400 with the not-free detail message
    """
    apartment = _make_hitas_free_apartment_after_period(
        apartment_state_of_sale=ApartmentStateOfSale.SOLD.value,
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Cannot reserve an apartment that is not free"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_for_reserved_apartment(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when the apartment is RESERVED.

    - POST returns 400 with the not-free detail message
    """
    apartment = _make_hitas_free_apartment_after_period(
        apartment_state_of_sale=ApartmentStateOfSale.RESERVED.value,
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Cannot reserve an apartment that is not free"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_for_reserved_haso_apartment(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when the apartment is RESERVED_HASO.

    - POST returns 400 with the not-free detail message
    """
    apartment = _make_hitas_free_apartment_after_period(
        apartment_state_of_sale=ApartmentStateOfSale.RESERVED_HASO.value,
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Cannot reserve an apartment that is not free"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_state_of_sale_missing(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when apartment_state_of_sale is
    missing/None.

    - POST returns 400 with the not-free detail message
    """
    apartment = _make_hitas_free_apartment_after_period(apartment_state_of_sale=None)
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Cannot reserve an apartment that is not free"
    )


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_apartment_not_found(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation returns 400 when get_apartment raises
    ObjectDoesNotExist.

    - POST returns 400 with the apartment-not-found detail message
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()

    with patch(
        "application_form.api.serializers.get_apartment",
        side_effect=ObjectDoesNotExist("Apartment does not exist"),
    ):
        response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext("Apartment not found")


@pytest.mark.django_db
def test_hitas_post_period_reservation_allowed_when_prior_reservation_canceled(
    api_client, elasticsearch
):
    """
    A canceled prior reservation does not block a HITAS post-period reservation.

    - POST returns 201
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile)
    existing_app_apartment = ApplicationApartmentFactory(
        apartment_uuid=apartment.uuid,
        application=ApplicationFactory(customer=customer, type=ApplicationType.HITAS),
    )
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        state=ApartmentReservationState.CANCELED,
        application_apartment=existing_app_apartment,
    )

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_for_sales_created_reservation(
    api_client, elasticsearch
):
    """
    A sales-created reservation (application_apartment=None) still blocks a
    HITAS post-period reservation via the customer FK.

    - POST returns 400 with the duplicate-reservation detail message
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile)
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        state=ApartmentReservationState.SUBMITTED,
        application_apartment=None,
    )

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert _detail_message(response) == gettext(
        "Customer already has a reservation in this project"
    )


@pytest.mark.django_db
def test_hitas_normal_period_application_still_allowed_multi_apartment(
    api_client, elasticsearch
):
    """
    Normal HITAS applications during the application period still allow multiple
    apartments and are not affected by the post-period logic.

    - POST returns 201 with two apartments
    """
    apartments = generate_apartments(
        elasticsearch,
        2,
        {
            "project_ownership_type": OwnershipType.HITAS.value,
            "project_can_apply_afterwards": True,
            "project_application_end_time": (
                datetime.now().replace(tzinfo=timezone.get_default_timezone())
                + timedelta(days=5)
            ),
            "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
        },
    )
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=apartments,
    )
    data["apartments"] = [
        {"priority": 0, "identifier": str(apartments[0].uuid)},
        {"priority": 1, "identifier": str(apartments[1].uuid)},
    ]

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code == 201
    application = Application.objects.get(external_uuid=data["application_uuid"])
    reservations = ApartmentReservation.objects.filter(
        application_apartment__application=application
    )
    assert reservations.count() == 2
    assert all(
        reservation.state == ApartmentReservationState.SUBMITTED
        for reservation in reservations
    )


@pytest.mark.django_db
def test_haso_late_apply_still_cancels_prior_reservation_unchanged(
    api_client, elasticsearch
):
    """
    The existing HASO late-apply behaviour (cancel prior reservation and create
    new one) must remain intact and not be affected by HITAS changes.

    - First HASO application creates reservation
    - Second HASO late application cancels the first and creates a new one
    """
    first_apartment, second_apartment = generate_apartments(
        elasticsearch,
        2,
        {
            "project_ownership_type": OwnershipType.HASO.value,
            "project_can_apply_afterwards": True,
            "project_application_end_time": (
                datetime.now().replace(tzinfo=timezone.get_default_timezone())
                - timedelta(days=1)
            ),
            "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
        },
    )

    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    first_data = create_application_data(
        profile,
        application_type=ApplicationType.HASO,
        apartments=[first_apartment],
    )
    first_data["apartments"] = [
        {"priority": 0, "identifier": str(first_apartment.uuid)}
    ]

    second_data = create_application_data(
        profile,
        application_type=ApplicationType.HASO,
        apartments=[second_apartment],
    )
    second_data["apartments"] = [
        {"priority": 0, "identifier": str(second_apartment.uuid)}
    ]

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response = api_client.post(
                reverse("application_form:application-list"),
                first_data,
                format="json",
            )
            assert response.status_code == 201
            first_application = Application.objects.get(
                external_uuid=first_data["application_uuid"]
            )

            response = api_client.post(
                reverse("application_form:application-list"),
                second_data,
                format="json",
            )

    assert response.status_code == 201

    first_reservation = ApartmentReservation.objects.get(
        apartment_uuid=first_apartment.uuid,
        application_apartment__application=first_application,
    )
    assert first_reservation.state == ApartmentReservationState.CANCELED

    second_application = Application.objects.get(
        external_uuid=second_data["application_uuid"]
    )
    second_reservation = ApartmentReservation.objects.get(
        apartment_uuid=second_apartment.uuid,
        application_apartment__application=second_application,
    )
    assert second_reservation.state == ApartmentReservationState.SUBMITTED


@pytest.mark.django_db
def test_hitas_post_period_reservation_creates_offer(api_client, elasticsearch):
    """
    A successful HITAS post-period reservation creates an offer for the customer.

    - Exactly one Offer exists for the new reservation
    - Offer is PENDING and valid for DEFAULT_OFFER_VALID_DAYS from today
    - Offer has not been messaged yet and has no handler (customer-initiated)
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, data = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201
    reservation = ApartmentReservation.objects.get(
        apartment_uuid=apartment.uuid,
        application_apartment__application__external_uuid=data["application_uuid"],
    )
    offer = Offer.objects.get(apartment_reservation=reservation)
    assert offer.state == OfferState.PENDING
    assert offer.valid_until == timezone.localdate() + timedelta(
        days=DEFAULT_OFFER_VALID_DAYS
    )
    assert offer.message_sent_at is None
    assert offer.handler == ""
    assert Offer.objects.count() == 1


@pytest.mark.django_db
def test_hitas_post_period_offer_is_delivered_via_pending_offer_messages(
    api_client, drupal_server_api_client, elasticsearch
):
    """
    The automatically created offer is delivered like any other offer.

    - GET pending_offer_messages returns the new offer
    - Recipients include the applying customer
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, _ = _post_hitas_reservation(api_client, profile, apartment)
    assert response.status_code == 201

    offer = Offer.objects.get(apartment_reservation__apartment_uuid=apartment.uuid)
    messages_response = drupal_server_api_client.get(
        reverse("application_form:pending_offer_messages"),
    )

    assert messages_response.status_code == 200
    assert [item["id"] for item in messages_response.data] == [offer.id]
    recipient_emails = {
        recipient["email"] for recipient in messages_response.data[0]["recipients"]
    }
    assert profile.email in recipient_emails


@pytest.mark.django_db
def test_sales_api_hitas_late_application_creates_offer_with_handler(
    api_client, elasticsearch
):
    """
    A late HITAS application made by a salesperson also creates an offer.

    - POST /v1/sales/applications/ with submitted_late returns 201
    - Reservation is OFFERED
    - Offer handler is the salesperson's full name
    """
    salesperson_profile = ProfileFactory()
    Group.objects.get(name__iexact=Roles.DRUPAL_SALESPERSON.name).user_set.add(
        salesperson_profile.user
    )
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_create_token(salesperson_profile)}"
    )
    apartment = _make_hitas_free_apartment_after_period()
    customer_profile = ProfileFactory()
    data = create_application_data(
        customer_profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]
    data["profile"] = customer_profile.id
    data["submitted_late"] = True

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response = api_client.post(
                reverse("application_form:sales-application-list"),
                data,
                format="json",
            )

    assert response.status_code == 201, response.data
    reservation = ApartmentReservation.objects.get(apartment_uuid=apartment.uuid)
    assert reservation.state == ApartmentReservationState.OFFERED
    assert reservation.offer.handler == salesperson_profile.full_name


@pytest.mark.django_db
def test_haso_late_application_creates_no_offer(api_client, elasticsearch):
    """
    HASO late applications keep their queue-based flow and get no offer.

    - POST returns 201
    - Reservation stays SUBMITTED
    - No Offer is created
    """
    apartment = make_late_haso_apartment()
    profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, _ = post_single_apartment_application(
                api_client, profile, apartment, ApplicationType.HASO
            )

    assert response.status_code == 201
    reservation = ApartmentReservation.objects.get(apartment_uuid=apartment.uuid)
    assert reservation.state == ApartmentReservationState.SUBMITTED
    assert not Offer.objects.exists()


@pytest.mark.django_db
def test_hitas_in_period_application_creates_no_offer(api_client, elasticsearch):
    """
    HITAS applications inside the application period get no offer.

    - POST returns 201
    - Reservation stays SUBMITTED
    - No Offer is created
    """
    apartment = _make_hitas_free_apartment_after_period(
        project_application_end_time=(
            datetime.now().replace(tzinfo=timezone.get_default_timezone())
            + timedelta(days=5)
        ),
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE.value,
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201
    reservation = ApartmentReservation.objects.get(apartment_uuid=apartment.uuid)
    assert reservation.state == ApartmentReservationState.SUBMITTED
    assert not Offer.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state_of_sale",
    [ApartmentStateOfSale.SOLD.value, ApartmentStateOfSale.RESERVED.value],
)
def test_rejected_hitas_post_period_reservation_creates_no_offer(
    api_client, elasticsearch, state_of_sale
):
    """
    A rejected HITAS post-period reservation leaves no offer or application.

    - POST returns 400
    - No Offer and no Application is created
    """
    apartment = _make_hitas_free_apartment_after_period(
        apartment_state_of_sale=state_of_sale
    )
    profile = ProfileFactory()

    response, data = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert not Offer.objects.exists()
    assert not Application.objects.filter(
        external_uuid=data["application_uuid"]
    ).exists()


@pytest.mark.django_db
def test_rejected_when_db_already_reserved_creates_no_offer(api_client, elasticsearch):
    """
    A HITAS post-period reservation blocked by an existing reserved reservation
    creates no offer.

    - POST returns 400
    - No Offer is created for the existing or the new reservation
    """
    apartment = _make_hitas_free_apartment_after_period()
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
        queue_position=1,
    )
    profile = ProfileFactory()

    response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 400
    assert not Offer.objects.exists()


@pytest.mark.django_db
@override_settings(SALES_NOTIFICATION_EMAIL=SALES_MAILBOX)
def test_hitas_post_period_email_sent_to_salesperson_and_sales_mailbox(
    api_client, elasticsearch
):
    """
    The HITAS late-reservation email goes to the salesperson and sales mailbox.

    - Exactly one email is sent
    - Recipients are the project estate agent and SALES_NOTIFICATION_EMAIL
    - Body contains the apartment address and the offer validity date
    """
    apartment = _make_hitas_free_apartment_after_period(
        project_estate_agent_email=AGENT_EMAIL
    )
    profile = ProfileFactory()

    with TestCase.captureOnCommitCallbacks(execute=True):
        response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [AGENT_EMAIL, SALES_MAILBOX]
    valid_until = timezone.localdate() + timedelta(days=DEFAULT_OFFER_VALID_DAYS)
    assert apartment.apartment_address in message.body
    assert valid_until.strftime("%-d.%-m.%Y") in message.body
    assert profile.email in message.body


@pytest.mark.django_db
@override_settings(SALES_NOTIFICATION_EMAIL=SALES_MAILBOX)
def test_hitas_post_period_email_sent_to_mailbox_when_agent_email_missing(
    api_client, elasticsearch
):
    """
    A missing estate agent email does not prevent the sales mailbox notification.

    - Exactly one email is sent, only to SALES_NOTIFICATION_EMAIL
    """
    apartment = _make_hitas_free_apartment_after_period(project_estate_agent_email="")
    profile = ProfileFactory()

    with TestCase.captureOnCommitCallbacks(execute=True):
        response, _ = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [SALES_MAILBOX]


@pytest.mark.django_db
@override_settings(SALES_NOTIFICATION_EMAIL=SALES_MAILBOX)
def test_haso_late_email_sent_only_to_salesperson(api_client, elasticsearch):
    """
    HASO late-application emails are unchanged and skip the sales mailbox.

    - Exactly one email is sent, only to the estate agent
    """
    apartment = make_late_haso_apartment(project_estate_agent_email=AGENT_EMAIL)
    profile = ProfileFactory()

    with TestCase.captureOnCommitCallbacks(execute=True):
        response, _ = post_single_apartment_application(
            api_client, profile, apartment, ApplicationType.HASO
        )

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [AGENT_EMAIL]


@pytest.mark.django_db
@override_settings(SALES_NOTIFICATION_EMAIL=SALES_MAILBOX)
def test_haso_late_email_skipped_when_no_recipients(api_client, elasticsearch, caplog):
    """
    A HASO late application without an estate agent email sends nothing.

    - POST returns 201
    - No email is sent
    - A warning is logged
    """
    apartment = make_late_haso_apartment(project_estate_agent_email="")
    profile = ProfileFactory()

    with caplog.at_level(logging.WARNING, logger="application_form"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, _ = post_single_apartment_application(
                api_client, profile, apartment, ApplicationType.HASO
            )

    assert response.status_code == 201
    assert len(mail.outbox) == 0
    assert any(
        "no recipients" in record.getMessage().lower() for record in caplog.records
    )


@override_settings(SALES_NOTIFICATION_EMAIL=SALES_MAILBOX)
@pytest.mark.parametrize(
    "ownership_type,agent_email,expected",
    [
        (OwnershipType.HITAS.value, AGENT_EMAIL, [AGENT_EMAIL, SALES_MAILBOX]),
        ("HITAS", AGENT_EMAIL, [AGENT_EMAIL, SALES_MAILBOX]),
        (OwnershipType.HITAS.value, "", [SALES_MAILBOX]),
        (OwnershipType.HITAS.value, None, [SALES_MAILBOX]),
        (OwnershipType.HITAS.value, SALES_MAILBOX, [SALES_MAILBOX]),
        (OwnershipType.HASO.value, AGENT_EMAIL, [AGENT_EMAIL]),
        (OwnershipType.HASO.value, "", []),
        (OwnershipType.PUOLIHITAS.value, AGENT_EMAIL, [AGENT_EMAIL]),
    ],
)
def test_get_sales_notification_recipients(ownership_type, agent_email, expected):
    """
    Recipients are resolved from the project and the sales mailbox setting.

    - HITAS adds SALES_NOTIFICATION_EMAIL (ownership type case-insensitive)
    - Empty or missing agent email is dropped
    - Duplicate addresses are collapsed
    - Non-HITAS projects get only the estate agent
    """
    project = SimpleNamespace(
        project_ownership_type=ownership_type,
        project_estate_agent_email=agent_email,
    )

    assert get_sales_notification_recipients(project) == expected


@override_settings(SALES_NOTIFICATION_EMAIL="")
def test_get_sales_notification_recipients_without_mailbox_setting():
    """
    An empty SALES_NOTIFICATION_EMAIL setting is ignored.

    - HITAS project gets only the estate agent
    """
    project = SimpleNamespace(
        project_ownership_type=OwnershipType.HITAS.value,
        project_estate_agent_email=AGENT_EMAIL,
    )

    assert get_sales_notification_recipients(project) == [AGENT_EMAIL]
