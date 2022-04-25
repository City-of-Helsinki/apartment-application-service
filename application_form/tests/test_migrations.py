import pytest
import uuid
from datetime import date

from application_form.enums import ApplicationType


@pytest.mark.django_db
def test_0050_populate_apartment_reservation_customer(migrator):
    old_state = migrator.apply_initial_migration(
        ("application_form", "0049_apartmentreservation_customer")
    )

    Profile = old_state.apps.get_model("users", "Profile")
    Customer = old_state.apps.get_model("customer", "Customer")
    Application = old_state.apps.get_model("application_form", "Application")
    ApplicationApartment = old_state.apps.get_model(
        "application_form", "ApplicationApartment"
    )
    ApartmentReservation = old_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )

    apartment_uuid = uuid.uuid4()
    profile = Profile.objects.create(date_of_birth=date.today())
    customer = Customer.objects.create(primary_profile=profile)
    application = Application.objects.create(
        external_uuid=uuid.uuid4(),
        applicants_count=1,
        type=ApplicationType.HASO,
        customer=customer,
    )
    application_apartment = ApplicationApartment.objects.create(
        application=application, apartment_uuid=apartment_uuid, priority_number=1
    )
    apartment_reservation = ApartmentReservation.objects.create(
        apartment_uuid=apartment_uuid,
        queue_position=1,
        application_apartment=application_apartment,
    )

    new_state = migrator.apply_tested_migration(
        ("application_form", "0050_populate_apartment_reservation_customer")
    )

    ApartmentReservation = new_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )
    apartment_reservation = ApartmentReservation.objects.get(
        id=apartment_reservation.id
    )
    assert apartment_reservation.customer.id == customer.id
    # Clean up record so tearDown migrations does not break
    apartment_reservation.delete()
