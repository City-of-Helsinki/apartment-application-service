"""
Tests for HITAS post-application-period reservations ("tee varaus").

After the application period has ended, a customer can make a reservation on a
free HITAS apartment when `project_can_apply_afterwards` is True. The rules are:
- Only one apartment per reservation (single apartment enforced)
- Apartment must not be sold
- Customer may not already have an active reservation in the project
- Salesperson email is sent on successful reservation
- HASO late-apply path is unchanged

Tests:
- Positive: HITAS free apartment after period with can_apply_afterwards
- Reject: period not ended (normal HITAS apply still works)
- Reject: can_apply_afterwards is False for HITAS
- Reject: more than one apartment submitted
- Reject: customer already has an active reservation in the project
- Reject: apartment is sold
- Email: salesperson notification sent on success
- HASO late apply unchanged (still cancels prior, still works)
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory, add_to_store
from application_form.enums import (
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models import ApartmentReservation, Application
from application_form.tests.conftest import (
    create_application_data,
    generate_apartments,
)
from application_form.tests.factories import (
    ApplicationApartmentFactory,
    ApplicationFactory,
    ApartmentReservationFactory,
)
from connections.enums import ApartmentStateOfSale
from customer.tests.factories import CustomerFactory
from users.tests.factories import ProfileFactory
from users.tests.utils import _create_token


def _make_hitas_free_apartment_after_period(**kwargs):
    """Create a single HITAS apartment past its application period that is
    free for reservations.

    Returns:
        ApartmentDocumentFactory: The created apartment document.
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


@pytest.mark.django_db
def test_hitas_post_period_reservation_succeeds(api_client, elasticsearch):
    """
    A customer can reserve a free HITAS apartment after the application period when
    project_can_apply_afterwards is True.

    - POST /v1/applications/ returns 201
    - ApartmentReservation is created with submitted state
    - Application is marked submitted_late
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    # Single apartment reservation
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]

    with patch(
        "application_form.api.serializers.send_sales_notification_email"
    ) as mock_email:
        response = api_client.post(
            reverse("application_form:application-list"), data, format="json"
        )

    assert response.status_code == 201
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert application.submitted_late is True
    reservation = ApartmentReservation.objects.get(
        apartment_uuid=apartment.uuid,
        application_apartment__application=application,
    )
    assert reservation.state == ApartmentReservationState.SUBMITTED
    mock_email.assert_called_once()


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
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]

    with patch(
        "application_form.api.serializers.send_sales_notification_email"
    ) as mock_email:
        response = api_client.post(
            reverse("application_form:application-list"), data, format="json"
        )

    assert response.status_code == 201
    assert mock_email.call_count == 1
    call_args = mock_email.call_args
    # First positional arg is the application
    application = Application.objects.get(external_uuid=data["application_uuid"])
    assert call_args[0][0] == application


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_can_apply_afterwards_false(
    api_client, elasticsearch
):
    """
    A HITAS late application is rejected when project_can_apply_afterwards is False.

    - POST returns non-201 status
    """
    apartment = _make_hitas_free_apartment_after_period(
        project_can_apply_afterwards=False
    )
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code != 201


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_with_multiple_apartments(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation with more than one apartment is rejected.

    - POST returns non-201 status
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
    # Explicitly send two apartments
    data["apartments"] = [
        {"priority": 0, "identifier": str(apartments[0].uuid)},
        {"priority": 1, "identifier": str(apartments[1].uuid)},
    ]

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code != 201


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_when_customer_already_has_reservation(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when the customer already has an
    active reservation in the same project.

    - POST returns non-201 status
    """
    apartment = _make_hitas_free_apartment_after_period()
    profile = ProfileFactory()
    customer = CustomerFactory(primary_profile=profile)
    # Create an existing submitted reservation for this customer in the same project
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

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code != 201


@pytest.mark.django_db
def test_hitas_post_period_reservation_rejected_for_sold_apartment(
    api_client, elasticsearch
):
    """
    A HITAS post-period reservation is rejected when the target apartment is sold.

    - POST returns non-201 status
    """
    apartment = _make_hitas_free_apartment_after_period(
        apartment_state_of_sale=ApartmentStateOfSale.SOLD.value,
    )
    profile = ProfileFactory()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")

    data = create_application_data(
        profile,
        application_type=ApplicationType.HITAS,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]

    response = api_client.post(
        reverse("application_form:application-list"), data, format="json"
    )

    assert response.status_code != 201


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
    first_data["apartments"] = [{"priority": 0, "identifier": str(first_apartment.uuid)}]

    response = api_client.post(
        reverse("application_form:application-list"), first_data, format="json"
    )
    assert response.status_code == 201
    first_application = Application.objects.get(
        external_uuid=first_data["application_uuid"]
    )

    second_data = create_application_data(
        profile,
        application_type=ApplicationType.HASO,
        apartments=[second_apartment],
    )
    second_data["apartments"] = [
        {"priority": 0, "identifier": str(second_apartment.uuid)}
    ]

    with patch("application_form.api.serializers.send_sales_notification_email"):
        response = api_client.post(
            reverse("application_form:application-list"), second_data, format="json"
        )

    assert response.status_code == 201

    first_reservation = ApartmentReservation.objects.get(
        apartment_uuid=first_apartment.uuid,
        application_apartment__application=first_application,
    )
    assert first_reservation.state == ApartmentReservationState.CANCELED
