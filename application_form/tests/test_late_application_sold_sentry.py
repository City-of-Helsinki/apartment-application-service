from unittest.mock import patch

import pytest

from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.services.application import create_application
from application_form.tests.conftest import (
    create_validated_application_data,
    prepare_metadata,
)
from application_form.tests.factories import ApartmentReservationFactory
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
@patch("application_form.services.application.sentry_sdk.capture_message")
def test_late_application_to_sold_apartment_reports_to_sentry(
    mock_capture_message,
    elastic_single_project_with_apartments,
):
    """
    A late application targeting a sold apartment must notify Sentry.

    - Uses the existing sold-reservation check (`_apartment_has_locked_winner`).
    - Application creation must still succeed; this is observability only.
    """
    apartments = elastic_single_project_with_apartments
    sold_apartment = apartments[0]

    ApartmentReservationFactory(
        apartment_uuid=sold_apartment.uuid,
        state=ApartmentReservationState.SOLD,
        list_position=1,
        queue_position=1,
    )

    profile = ProfileFactory()
    data = create_validated_application_data(
        profile, ApplicationType.HASO, num_applicants=1
    )
    data["apartments"] = [{"priority": 0, "identifier": sold_apartment.uuid}]
    data = prepare_metadata(data, profile)

    application = create_application(data, submitted_late=True)

    mock_capture_message.assert_called_once_with(
        "Late application submitted to sold apartment",
        level="warning",
    )
    assert application.submitted_late is True


@pytest.mark.django_db
@patch("application_form.services.application.sentry_sdk.capture_message")
def test_late_application_to_unsold_apartment_does_not_report_to_sentry(
    mock_capture_message,
    elastic_single_project_with_apartments,
):
    """
    Late applications to apartments without a sold reservation must stay silent.

    - No Sentry message when the apartment queue has no sold winner.
    """
    apartments = elastic_single_project_with_apartments
    free_apartment = apartments[1]

    profile = ProfileFactory()
    data = create_validated_application_data(
        profile, ApplicationType.HASO, num_applicants=1
    )
    data["apartments"] = [{"priority": 0, "identifier": free_apartment.uuid}]
    data = prepare_metadata(data, profile)

    create_application(data, submitted_late=True)

    mock_capture_message.assert_not_called()


@pytest.mark.django_db
@patch("application_form.services.application.sentry_sdk.capture_message")
def test_on_time_application_to_sold_apartment_does_not_report_to_sentry(
    mock_capture_message,
    elastic_single_project_with_apartments,
):
    """
    On-time applications must not trigger the sold-apartment Sentry alert.

    - Only late (`submitted_late=True`) submissions are in scope.
    """
    apartments = elastic_single_project_with_apartments
    sold_apartment = apartments[0]

    ApartmentReservationFactory(
        apartment_uuid=sold_apartment.uuid,
        state=ApartmentReservationState.SOLD,
        list_position=1,
        queue_position=1,
    )

    profile = ProfileFactory()
    data = create_validated_application_data(
        profile, ApplicationType.HASO, num_applicants=1
    )
    data["apartments"] = [{"priority": 0, "identifier": sold_apartment.uuid}]
    data = prepare_metadata(data, profile)

    create_application(data, submitted_late=False)

    mock_capture_message.assert_not_called()


@pytest.mark.django_db
@patch("application_form.services.application.sentry_sdk.capture_message")
def test_late_application_to_sold_apartment_includes_context_in_sentry_scope(
    mock_capture_message,
    elastic_single_project_with_apartments,
):
    """
    Sentry context must identify the application and sold apartment UUIDs.

    - Context is attached inside a isolated scope before capture_message.
    """
    apartments = elastic_single_project_with_apartments
    sold_apartment = apartments[0]

    ApartmentReservationFactory(
        apartment_uuid=sold_apartment.uuid,
        state=ApartmentReservationState.SOLD,
        list_position=1,
        queue_position=1,
    )

    profile = ProfileFactory()
    data = create_validated_application_data(
        profile, ApplicationType.HASO, num_applicants=1
    )
    data["apartments"] = [{"priority": 0, "identifier": sold_apartment.uuid}]
    data = prepare_metadata(data, profile)

    with patch(
        "application_form.services.application.sentry_sdk.push_scope"
    ) as mock_push_scope:
        scope = mock_push_scope.return_value.__enter__.return_value
        create_application(data, submitted_late=True)

    scope.set_context.assert_called_once_with(
        "late_application_to_sold_apartment",
        {
            "application_external_uuid": str(data["external_uuid"]),
            "sold_apartment_uuids": [str(sold_apartment.uuid)],
        },
    )
    mock_capture_message.assert_called_once()
