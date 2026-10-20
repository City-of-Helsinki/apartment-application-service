"""
Seed HASO reservation queue scenarios for the E2E stack.

Each scenario gets its own HASO apartment (from the Drupal search API) with a
lottery event, an "existing" e2e customer holding a non-late reservation at
queue position 1 (right of residence 500), and a "new" e2e customer without a
reservation (right of residence 100). The sales UI spec then adds the new
customer to the queue and checks the resulting position.

E2E customers are identified by primary profile emails in the reserved
e2e.invalid domain. Re-running resets only e2e data, never other rows.

Prints the seeded data as JSON (keyed by scenario) to stdout on success;
diagnostics go to stderr.

Usage: python django_e2e_seed_haso_queue.py

The Django project must be importable (e.g. PYTHONPATH=/app in the
container) since this script lives outside the project directory.
"""

import datetime
import json
import os
import sys

USAGE = "Usage: python django_e2e_seed_haso_queue.py"

SCENARIOS = ("on_time", "late")
E2E_EMAIL_DOMAIN = "e2e.invalid"
ROLES = ("existing", "new")
HASO_OWNERSHIP_TYPE = "haso"
RIGHT_OF_RESIDENCE = {"existing": 500, "new": 100}
FIRST_NAMES = {"existing": "Existing", "new": "Newcomer"}
# Distinct per scenario and role, and none contains another, so a customer
# search or a text lookup in one scenario never matches another customer.
LAST_NAMES = {
    ("on_time", "existing"): "E2eHasoOntimeExisting",
    ("on_time", "new"): "E2eHasoOntimeNewcomer",
    ("late", "existing"): "E2eHasoLateExisting",
    ("late", "new"): "E2eHasoLateNewcomer",
}
HANDLER = "E2E seed"


def get_projects(**filters):
    """
    Return project documents from the Drupal search API.

    Module-level so tests can replace it; imports lazily so importing this
    module needs no configured Django.

            Parameters:
                    **filters: Search API filters

            Returns:
                    projects (list): Project documents
    """
    from apartment.elastic.queries import get_projects as query_projects

    return query_projects(**filters)


def get_apartments(project_uuid=None, include_project_fields=False, **filters):
    """
    Return apartment documents from the Drupal search API.

    Module-level so tests can replace it; imports lazily so importing this
    module needs no configured Django.

            Parameters:
                    project_uuid (str | None): Limit to one project's apartments
                    include_project_fields (bool): Include project fields
                    **filters: Search API filters

            Returns:
                    apartments (list): Apartment documents
    """
    from apartment.elastic.queries import get_apartments as query_apartments

    return query_apartments(
        project_uuid=project_uuid,
        include_project_fields=include_project_fields,
        **filters,
    )


def _validate_scenario(scenario):
    """
    Raise ValueError unless the scenario is one of SCENARIOS.

            Parameters:
                    scenario (str): Scenario name
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; expected one of {SCENARIOS}")


def _email(scenario, role):
    """
    Return the primary profile email of a scenario's e2e customer.

            Parameters:
                    scenario (str): Scenario name
                    role (str): "existing" or "new"

            Returns:
                    email (str): The e2e customer's email
    """
    return f"haso-{scenario}-{role}@{E2E_EMAIL_DOMAIN}"


def _is_e2e_email(email):
    """
    Return whether an email belongs to the e2e email domain.

            Parameters:
                    email (str | None): Email address

            Returns:
                    is_e2e (bool): True if the email ends with @E2E_EMAIL_DOMAIN
    """
    return (email or "").lower().endswith(f"@{E2E_EMAIL_DOMAIN}")


def is_e2e_reservation(reservation):
    """
    Return whether a reservation belongs to an e2e customer.

            Parameters:
                    reservation (ApartmentReservation): Reservation with its
                    customer's primary profile available

            Returns:
                    is_e2e (bool): True if the customer's primary profile email
                    is in the e2e email domain
    """
    return _is_e2e_email(reservation.customer.primary_profile.email)


def _is_haso(document):
    """
    Return whether a project or apartment document is of a HASO project.

            Parameters:
                    document: Project or apartment document

            Returns:
                    is_haso (bool): True if project_ownership_type is HASO
    """
    ownership_type = getattr(document, "project_ownership_type", None) or ""
    return ownership_type.lower() == HASO_OWNERSHIP_TYPE


def _free_apartments(apartments):
    """
    Return the apartments that have no reservations of non-e2e customers.

    Uses a single reservation query for the whole batch.

            Parameters:
                    apartments (list): Apartment documents

            Returns:
                    free (list): Apartments, in the given order, whose
                    reservations (canceled included) all belong to e2e customers
    """
    from application_form.models import ApartmentReservation

    if not apartments:
        return []
    reservations = ApartmentReservation.objects.filter(
        apartment_uuid__in=[str(apartment.uuid) for apartment in apartments]
    ).select_related("customer__primary_profile")
    taken = {
        str(reservation.apartment_uuid)
        for reservation in reservations
        if not is_e2e_reservation(reservation)
    }
    return [apartment for apartment in apartments if str(apartment.uuid) not in taken]


def select_apartments(count):
    """
    Select HASO apartments that only e2e customers have reserved.

    Apartments are ordered by (project uuid, apartment uuid) so repeated runs
    pick the same apartments.

            Parameters:
                    count (int): Number of apartments to select

            Returns:
                    apartments (list): The first `count` eligible apartments

            Raises:
                    RuntimeError: If fewer than `count` eligible apartments exist
    """
    projects = sorted(
        (project for project in get_projects() if _is_haso(project)),
        key=lambda project: str(project.project_uuid),
    )
    selected = []
    for project in projects:
        apartments = sorted(
            (
                apartment
                for apartment in get_apartments(
                    project_uuid=project.project_uuid, include_project_fields=True
                )
                if getattr(apartment, "uuid", None)
            ),
            key=lambda apartment: str(apartment.uuid),
        )
        for apartment in _free_apartments(apartments):
            selected.append(apartment)
            if len(selected) == count:
                return selected
    raise RuntimeError(
        f"Found {len(selected)} HASO apartments without non-e2e reservations, "
        f"{count} needed"
    )


def reset_scenario(scenario):
    """
    Delete a scenario's e2e customers, their profiles and reservations.

    Only rows tied to the scenario's e2e emails are deleted. Idempotent.

            Parameters:
                    scenario (str): Scenario name

            Raises:
                    ValueError: If the scenario is unknown
    """
    _validate_scenario(scenario)

    from django.db import transaction
    from django.db.models import Q

    from application_form.models import ApartmentReservation
    from customer.models import Customer
    from users.models import Profile

    emails = [_email(scenario, role) for role in ROLES]
    with transaction.atomic():
        profiles = Profile.objects.filter(email__in=emails)
        customers = Customer.objects.filter(
            Q(primary_profile__in=profiles) | Q(secondary_profile__in=profiles)
        )
        ApartmentReservation.objects.filter(customer__in=customers).delete()
        customers.delete()
        profiles.delete()


def _create_customer(scenario, role):
    """
    Create an e2e customer and its primary profile.

            Parameters:
                    scenario (str): Scenario name
                    role (str): "existing" or "new"

            Returns:
                    customer (Customer): The created customer
    """
    from customer.models import Customer
    from users.models import Profile

    profile = Profile.objects.create(
        first_name=FIRST_NAMES[role],
        last_name=LAST_NAMES[(scenario, role)],
        email=_email(scenario, role),
        phone_number="+358 40 000 0000",
        street_address="E2E-katu 1",
        city="Helsinki",
        postal_code="00100",
        date_of_birth=datetime.date(1980, 1, 1),
        contact_language="fi",
    )
    return Customer.objects.create(
        primary_profile=profile,
        right_of_residence=RIGHT_OF_RESIDENCE[role],
        right_of_residence_is_old_batch=False,
    )


def _customer_data(customer):
    """
    Return the JSON-serializable identity of a customer.

            Parameters:
                    customer (Customer): Customer

            Returns:
                    data (dict): id, first_name and last_name
    """
    return {
        "id": customer.id,
        "first_name": customer.primary_profile.first_name,
        "last_name": customer.primary_profile.last_name,
    }


def seed_scenario(scenario, apartment):
    """
    Reset and seed a scenario on an apartment.

    Removes the scenario's previous e2e data and any e2e reservations on the
    apartment, ensures a lottery event exists for the apartment, then creates
    the existing customer (non-late reservation at queue and list position 1)
    and the new customer (no reservation).

            Parameters:
                    scenario (str): Scenario name
                    apartment: Apartment document (uuid, project_uuid,
                    apartment_number)

            Returns:
                    data (dict): JSON-serializable scenario, project, apartment
                    and customer identities

            Raises:
                    ValueError: If the scenario is unknown
    """
    _validate_scenario(scenario)

    from django.db import transaction

    from application_form.enums import ApartmentReservationState
    from application_form.models import ApartmentReservation, LotteryEvent

    apartment_uuid = str(apartment.uuid)
    with transaction.atomic():
        reset_scenario(scenario)
        apartment_reservations = ApartmentReservation.objects.filter(
            apartment_uuid=apartment_uuid
        ).select_related("customer__primary_profile")
        e2e_ids = [r.pk for r in apartment_reservations if is_e2e_reservation(r)]
        ApartmentReservation.objects.filter(pk__in=e2e_ids).delete()

        if not LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).exists():
            LotteryEvent.objects.create(apartment_uuid=apartment_uuid, handler=HANDLER)

        existing = _create_customer(scenario, "existing")
        new = _create_customer(scenario, "new")
        ApartmentReservation.objects.create(
            apartment_uuid=apartment_uuid,
            customer=existing,
            queue_position=1,
            list_position=1,
            state=ApartmentReservationState.SUBMITTED,
            right_of_residence=existing.right_of_residence,
            right_of_residence_is_old_batch=False,
            submitted_late=False,
            handler=HANDLER,
        )

    return {
        "scenario": scenario,
        "project_uuid": str(apartment.project_uuid),
        "apartment_uuid": apartment_uuid,
        "apartment_number": apartment.apartment_number,
        "existing_customer": _customer_data(existing),
        "new_customer": _customer_data(new),
    }


def main(argv=None):
    """
    Seed every scenario on its own apartment and print the result as JSON.

    Apartments are selected before anything is reset or seeded, so a missing
    apartment leaves the database untouched.

            Parameters:
                    argv (list[str] | None): Must be empty; defaults to
                    sys.argv[1:]

            Returns:
                    exit_code (int): 0 on success, 1 if too few apartments
                    exist, 2 on unexpected arguments
    """
    args = sys.argv[1:] if argv is None else argv
    if args:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        apartments = select_apartments(len(SCENARIOS))
    except RuntimeError as error:
        print(f"[e2e] Cannot seed HASO queue scenarios: {error}", file=sys.stderr)
        return 1

    from django.db import transaction

    with transaction.atomic():
        result = {
            scenario: seed_scenario(scenario, apartment)
            for scenario, apartment in zip(SCENARIOS, apartments)
        }

    print(json.dumps(result, indent=2))
    print(f"[e2e] HASO queue scenarios seeded: {', '.join(SCENARIOS)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "apartment_application_service.settings"
    )
    import django

    django.setup()
    sys.exit(main())
