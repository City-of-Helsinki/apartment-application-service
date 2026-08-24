"""
Tests for HITAS post-application-period reservations ("tee varaus").

After the application period has ended, a customer can make a reservation on a
free HITAS apartment when `project_can_apply_afterwards` is True. The rules are:
- Only one apartment per reservation (single apartment enforced)
- Apartment must be FREE_FOR_RESERVATIONS
- Successful reservation is marked RESERVED (apartment is no longer free)
- Customer may not already have an active reservation in the project
- Salesperson email is sent on successful reservation
- HASO late-apply path is unchanged

Tests:
- Positive: HITAS free apartment after period with can_apply_afterwards
- Positive: reservation and apartment are marked RESERVED
- Positive: Drupal apartment_states reports RESERVED
- Positive: stays SUBMITTED when another reserved reservation exists
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

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from apartment.enums import ApartmentState, OwnershipType
from apartment.tests.factories import add_to_store, ApartmentDocumentFactory
from apartment.utils import get_apartment_state_from_apartment_uuid
from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models import ApartmentReservation, Application
from application_form.tests.conftest import create_application_data, generate_apartments
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
    LotteryEventFactory,
)
from connections.enums import ApartmentStateOfSale
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


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
    - ApartmentReservation is created with reserved state
    - Apartment derived state is reserved
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
    assert reservation.state == ApartmentReservationState.RESERVED
    assert reservation.state_change_events.filter(
        state=ApartmentReservationState.RESERVED
    ).exists()
    assert (
        get_apartment_state_from_apartment_uuid(apartment.uuid)
        == ApartmentState.RESERVED.value
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
def test_hitas_post_period_reservation_stays_submitted_when_already_reserved(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation stays SUBMITTED when another reserved
    reservation already exists for the apartment.

    This is a defensive case: the public API rejects non-free apartments, but
    salesperson-created late reservations use the same rule.

    - Existing reserved reservation is unchanged
    - New reservation is SUBMITTED
    - Apartment derived state stays reserved
    """
    apartment = _make_hitas_free_apartment_after_period()
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
        queue_position=1,
    )
    profile = ProfileFactory()

    with patch("application_form.api.serializers.send_sales_notification_email"):
        with TestCase.captureOnCommitCallbacks(execute=True):
            response, data = _post_hitas_reservation(api_client, profile, apartment)

    assert response.status_code == 201
    application = Application.objects.get(external_uuid=data["application_uuid"])
    new_reservation = ApartmentReservation.objects.get(
        apartment_uuid=apartment.uuid,
        application_apartment__application=application,
    )
    assert new_reservation.state == ApartmentReservationState.SUBMITTED
    assert (
        get_apartment_state_from_apartment_uuid(apartment.uuid)
        == ApartmentState.RESERVED.value
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
