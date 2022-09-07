import pytest

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import ApartmentReservationState
from application_form.tests.factories import ApartmentReservationFactory


@pytest.mark.django_db
def test_apartment_reservation_gets_state_change_event_on_creation():
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )
    assert reservation.state_change_events.count() == 1
    assert (
        reservation.state_change_events.first().state
        == ApartmentReservationState.SUBMITTED
    )
