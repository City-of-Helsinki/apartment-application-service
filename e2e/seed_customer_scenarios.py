"""
Create the Django side of the e2e customer scenarios (customers.json).

For every customer with an application this creates a customer, an
application (external_uuid == the scenario backend_uuid, which is also the
Drupal application's field_backend_id), its primary applicant, one
application apartment and a reservation in the scenario state, with the
state change history a real reservation would have.

The profile is looked up by email; it is created by
e2e/fixtures/drupal/load_customers.php through the backend API, so that
script must run first. Run after load_django_fixtures.py, which deletes the
reservations on the baseline apartments.

Usage: python seed_customer_scenarios.py

The Django project must be importable (e.g. PYTHONPATH=/app in the
container) since this script lives outside the project directory.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
BASELINE_FILE = FIXTURES_DIR / "drupal" / "baseline.json"
CUSTOMERS_FILE = FIXTURES_DIR / "drupal" / "customers.json"
HANDLER = "E2E seed"


def apartment_uuids_by_key():
    """
    Map baseline apartment keys to apartment uuids.

            Returns:
                    uuids (dict[str, str]): Apartment uuid by apartment key
    """
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return {
        apartment["key"]: apartment["uuid"]
        for project in data["projects"]
        for apartment in project["apartments"]
    }


def seed_customer(customer, apartment_uuid):
    """
    Recreate one customer's application and reservation.

            Parameters:
                    customer (dict): Scenario entry from customers.json
                    apartment_uuid (str): Uuid of the applied apartment
    """
    from application_form.enums import (
        ApartmentReservationCancellationReason,
        ApartmentReservationState,
        ApplicationType,
    )
    from application_form.models import (
        ApartmentReservation,
        Applicant,
        Application,
        ApplicationApartment,
    )
    from customer.models import Customer
    from users.models import Profile

    scenario = customer["application"]
    profile = (
        Profile.objects.filter(email=customer["email"]).order_by("-created_at").first()
    )
    if profile is None:
        raise RuntimeError(
            f"No Django profile for {customer['email']}; run load_customers.php first"
        )

    Application.objects.filter(external_uuid=scenario["backend_uuid"]).delete()
    db_customer, _ = Customer.objects.get_or_create(
        primary_profile=profile, secondary_profile=None
    )

    application = Application.objects.create(
        external_uuid=scenario["backend_uuid"],
        customer=db_customer,
        applicants_count=1,
        type=ApplicationType.HITAS,
        process_number="",
        handler_information="",
        sender_names=f"{customer['first_name']} {customer['last_name']}",
    )
    date_of_birth = date.fromisoformat(customer["date_of_birth"])
    Applicant.objects.create(
        application=application,
        is_primary_applicant=True,
        first_name=customer["first_name"],
        last_name=customer["last_name"],
        email=customer["email"],
        phone_number="+358 40 000 0000",
        street_address="E2E-katu 1",
        city="Helsinki",
        postal_code="00100",
        age=date.today().year - date_of_birth.year,
        date_of_birth=date_of_birth,
        ssn_suffix=customer["national_identification_number"][6:],
        contact_language="fi",
    )
    application_apartment = ApplicationApartment.objects.create(
        application=application, apartment_uuid=apartment_uuid, priority_number=1
    )

    # save() records the initial "submitted" state change event.
    reservation = ApartmentReservation.objects.create(
        apartment_uuid=apartment_uuid,
        customer=db_customer,
        application_apartment=application_apartment,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.SUBMITTED,
        handler=HANDLER,
    )
    state = ApartmentReservationState(scenario["reservation_state"])
    if state == ApartmentReservationState.CANCELED:
        reason = scenario.get("cancellation_reason")
        reservation.queue_position_before_cancelation = reservation.queue_position
        reservation.save(update_fields=("queue_position_before_cancelation",))
        reservation.set_state(
            ApartmentReservationState.CANCELED,
            cancellation_reason=(
                ApartmentReservationCancellationReason(reason) if reason else None
            ),
            queue_position=None,
        )
        reservation.queue_position = None
        reservation.save(update_fields=("queue_position",))
    elif state != ApartmentReservationState.SUBMITTED:
        reservation.set_state(state)
    print(
        f"[e2e-customers] {customer['key']}: application={application.external_uuid} "
        f"reservation={reservation.pk} state={state.value}"
    )


def main():
    """
    Seed every customer scenario that has an application, in one transaction.
    """
    from django.db import transaction

    customers = json.loads(CUSTOMERS_FILE.read_text(encoding="utf-8"))["customers"]
    apartments = apartment_uuids_by_key()
    with transaction.atomic():
        for customer in customers:
            if customer["application"] is not None:
                seed_customer(
                    customer, apartments[customer["application"]["apartment"]]
                )


if __name__ == "__main__":
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "apartment_application_service.settings"
    )
    import django

    django.setup()
    sys.exit(main())
