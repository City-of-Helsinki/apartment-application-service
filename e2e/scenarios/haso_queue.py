"""
The "haso_queue" scenario: a HASO apartment after the lottery.

Seeds, on a baseline HASO apartment, a lottery event and an "existing"
customer holding a non-late reservation at queue position 1 (right of
residence 500), plus a "new" customer without a reservation (right of
residence 100). tests-e2e/tests/sales-ui/haso-reservation-queue.spec.ts then
adds the new customer to the queue and checks the resulting position.

Params:
    variant (str): "on_time" or "late"; selects the default apartment
    namespace (str): ^[a-z0-9-]{1,40}$, embedded in the customer names
    apartment_key (str, optional): baseline HASO apartment overriding the
        variant's default apartment

Every run resets the apartment (all its reservations and their dependent
rows) and the namespace's previous customers of the variant, so a test can
seed it again without leftovers. Customers of other namespaces and other
apartments are left untouched.

Django is imported lazily so the scenario can be registered (and its params
validated) without a configured Django project.
"""

import datetime
import re

from e2e.scenarios.baseline import load_baseline, UUID_PREFIX
from e2e.scenarios.registry import scenario, ScenarioParamsError

SCENARIO_NAME = "haso_queue"
# Baseline apartment each variant runs on by default. Distinct apartments let
# the variants run in parallel without resetting each other's data.
VARIANT_APARTMENTS = {"on_time": "haso-a1", "late": "haso-a2"}
HASO_OWNERSHIP_TYPE = "HASO"
NAMESPACE_PATTERN = re.compile(r"[a-z0-9-]{1,40}")
ALLOWED_PARAMS = frozenset({"variant", "namespace", "apartment_key"})
REQUIRED_PARAMS = ("variant", "namespace")

ROLES = ("existing", "new")
RIGHT_OF_RESIDENCE = {"existing": 500, "new": 100}
FIRST_NAMES = {"existing": "Existing", "new": "Newcomer"}
# Combined with the namespace into last names such as
# "E2e-w0-1a2b3c4d5e-HasoOntimeExisting". No suffix contains another, so a
# customer search for one last name never matches the other role or variant.
LAST_NAME_SUFFIXES = {
    ("on_time", "existing"): "HasoOntimeExisting",
    ("on_time", "new"): "HasoOntimeNewcomer",
    ("late", "existing"): "HasoLateExisting",
    ("late", "new"): "HasoLateNewcomer",
}
E2E_EMAIL_DOMAIN = "e2e.invalid"
HANDLER = "E2E seed"


def _require_string(params, name):
    """
    Return a param that must be a string.

            Parameters:
                    params (dict): Scenario params
                    name (str): Param name

            Returns:
                    value (str): The param value

            Raises:
                    ScenarioParamsError: If the value is not a string
    """
    value = params[name]
    if not isinstance(value, str):
        raise ScenarioParamsError(f"{name} must be a string, got {value!r}")
    return value


def _validate_apartment_key(baseline, apartment_key):
    """
    Raise unless the key names a HASO apartment of the baseline.

            Parameters:
                    baseline (Baseline): Loaded baseline
                    apartment_key (str): Requested apartment key

            Raises:
                    ScenarioParamsError: If the key is unknown or not HASO
    """
    try:
        apartment = baseline.apartment(apartment_key)
    except KeyError:
        raise ScenarioParamsError(
            f"apartment_key {apartment_key!r} is not a baseline apartment"
        ) from None
    ownership_type = baseline.project(apartment["project_key"])["ownership_type"]
    if ownership_type != HASO_OWNERSHIP_TYPE:
        raise ScenarioParamsError(
            f"apartment_key {apartment_key!r} is not a HASO apartment"
        )


def validate_params(params, baseline):
    """
    Validate scenario params without touching the database.

            Parameters:
                    params: Params received from the caller
                    baseline (Baseline): Loaded baseline

            Returns:
                    validated (tuple): (variant, namespace, apartment key); the
                    key is the variant's default unless apartment_key is given

            Raises:
                    ScenarioParamsError: If any param is missing or invalid
    """
    if not isinstance(params, dict):
        raise ScenarioParamsError("params must be a JSON object")
    unknown = sorted(str(key) for key in set(params) - ALLOWED_PARAMS)
    if unknown:
        raise ScenarioParamsError(f"unknown params: {', '.join(unknown)}")
    missing = [name for name in REQUIRED_PARAMS if name not in params]
    if missing:
        raise ScenarioParamsError(f"missing params: {', '.join(missing)}")
    variant = _require_string(params, "variant")
    if variant not in VARIANT_APARTMENTS:
        raise ScenarioParamsError(
            f"variant must be one of {', '.join(VARIANT_APARTMENTS)}, got {variant!r}"
        )
    namespace = _require_string(params, "namespace")
    if not NAMESPACE_PATTERN.fullmatch(namespace):
        raise ScenarioParamsError(
            f"namespace must match ^[a-z0-9-]{{1,40}}$, got {namespace!r}"
        )
    if "apartment_key" not in params:
        return variant, namespace, VARIANT_APARTMENTS[variant]
    apartment_key = _require_string(params, "apartment_key")
    _validate_apartment_key(baseline, apartment_key)
    return variant, namespace, apartment_key


def _guard_e2e_apartment(apartment_uuid):
    """
    Refuse to touch an apartment that is not baseline e2e content.

            Parameters:
                    apartment_uuid (str): Apartment uuid

            Raises:
                    RuntimeError: If the uuid does not start with UUID_PREFIX
    """
    if not str(apartment_uuid).startswith(UUID_PREFIX):
        raise RuntimeError(
            f"Refusing to seed apartment {apartment_uuid}: e2e apartment uuids "
            f"start with {UUID_PREFIX!r}"
        )


def _email(variant, namespace, role):
    """
    Return the email identifying a scenario customer.

    Dots never occur in variants, namespaces or roles, so the address is
    unique per (variant, namespace, role).

            Parameters:
                    variant (str): Scenario variant
                    namespace (str): Scenario namespace
                    role (str): "existing" or "new"

            Returns:
                    email (str): Address in the reserved e2e.invalid domain
    """
    return f"haso-queue.{variant}.{namespace}.{role}@{E2E_EMAIL_DOMAIN}"


def _last_name(variant, namespace, role):
    """
    Return the last name of a scenario customer.

            Parameters:
                    variant (str): Scenario variant
                    namespace (str): Scenario namespace
                    role (str): "existing" or "new"

            Returns:
                    last_name (str): Name embedding the namespace
    """
    return f"E2e-{namespace}-{LAST_NAME_SUFFIXES[(variant, role)]}"


def _delete_reservations(reservations):
    """
    Delete reservations together with the rows that protect them.

            Parameters:
                    reservations (QuerySet): ApartmentReservation queryset
    """
    from application_form.models import ApartmentReservation, Offer
    from cost_index.models import ApartmentRevaluation
    from invoicing.models import (
        ApartmentInstallment,
        DrupalPaymentSyncOutboxEvent,
        Payment,
    )

    ids = list(reservations.values_list("pk", flat=True))
    if not ids:
        return
    installment_filter = {"apartment_installment__apartment_reservation_id__in": ids}
    Payment.objects.filter(**installment_filter).delete()
    DrupalPaymentSyncOutboxEvent.objects.filter(**installment_filter).delete()
    ApartmentInstallment.objects.filter(apartment_reservation_id__in=ids).delete()
    ApartmentRevaluation.objects.filter(apartment_reservation_id__in=ids).delete()
    Offer.objects.filter(apartment_reservation_id__in=ids).delete()
    ApartmentReservation.objects.filter(pk__in=ids).delete()


def _reset(apartment_uuid, variant, namespace):
    """
    Delete the apartment's reservations and the namespace's variant customers.

    Customers owning other reservations on the apartment are kept; only
    their reservations are deleted.

            Parameters:
                    apartment_uuid (str): Scenario apartment uuid
                    variant (str): Scenario variant
                    namespace (str): Scenario namespace
    """
    from django.db.models import Q

    from application_form.models import ApartmentReservation, LotteryEventResult
    from customer.models import Customer
    from users.models import Profile

    emails = [_email(variant, namespace, role) for role in ROLES]
    profiles = Profile.objects.filter(email__in=emails)
    customers = Customer.objects.filter(
        Q(primary_profile__in=profiles) | Q(secondary_profile__in=profiles)
    )
    _delete_reservations(
        ApartmentReservation.objects.filter(
            Q(apartment_uuid=apartment_uuid) | Q(customer__in=customers)
        )
    )
    # Deleting a customer cascades to its applications, whose apartments are
    # protected by lottery results.
    LotteryEventResult.objects.filter(
        application_apartment__application__customer__in=customers
    ).delete()
    customers.delete()
    profiles.delete()


def _ensure_single_lottery_event(apartment_uuid):
    """
    Leave exactly one lottery event on the apartment.

    Keeps the oldest event if any exist, otherwise creates one.

            Parameters:
                    apartment_uuid (str): Apartment uuid
    """
    from application_form.models import LotteryEvent

    events = LotteryEvent.objects.filter(apartment_uuid=apartment_uuid)
    first_pk = events.order_by("pk").values_list("pk", flat=True).first()
    if first_pk is None:
        LotteryEvent.objects.create(apartment_uuid=apartment_uuid, handler=HANDLER)
    else:
        events.exclude(pk=first_pk).delete()


def _create_customer(variant, namespace, role):
    """
    Create a scenario customer and its primary profile.

            Parameters:
                    variant (str): Scenario variant
                    namespace (str): Scenario namespace
                    role (str): "existing" or "new"

            Returns:
                    customer (Customer): The created customer
    """
    from customer.models import Customer
    from users.models import Profile

    profile = Profile.objects.create(
        first_name=FIRST_NAMES[role],
        last_name=_last_name(variant, namespace, role),
        email=_email(variant, namespace, role),
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


def _create_existing_reservation(apartment_uuid, customer):
    """
    Create the existing customer's non-late reservation at position 1.

            Parameters:
                    apartment_uuid (str): Apartment uuid
                    customer (Customer): The existing customer

            Returns:
                    reservation (ApartmentReservation): The created reservation
    """
    from application_form.enums import ApartmentReservationState
    from application_form.models import ApartmentReservation

    return ApartmentReservation.objects.create(
        apartment_uuid=apartment_uuid,
        customer=customer,
        queue_position=1,
        list_position=1,
        state=ApartmentReservationState.SUBMITTED,
        right_of_residence=customer.right_of_residence,
        right_of_residence_is_old_batch=False,
        submitted_late=False,
        handler=HANDLER,
    )


def _customer_data(customer):
    """
    Return the JSON-serializable identity of a customer.

            Parameters:
                    customer (Customer): Customer with its primary profile

            Returns:
                    data (dict): id, first_name and last_name
    """
    return {
        "id": customer.pk,
        "first_name": customer.primary_profile.first_name,
        "last_name": customer.primary_profile.last_name,
    }


@scenario(SCENARIO_NAME)
def seed_haso_queue(params):
    """
    Reset and seed the HASO queue scenario.

            Parameters:
                    params (dict): variant, namespace and optional apartment_key

            Returns:
                    manifest (dict): scenario, variant, namespace, project_uuid,
                    apartment_uuid, apartment_number, existing_customer and
                    new_customer (each id, first_name, last_name)

            Raises:
                    ScenarioParamsError: If params are invalid (nothing written)
                    RuntimeError: If the apartment is not e2e content (nothing
                    written)
    """
    baseline = load_baseline()
    variant, namespace, apartment_key = validate_params(params, baseline)
    apartment = baseline.apartment(apartment_key)
    apartment_uuid = apartment["uuid"]
    _guard_e2e_apartment(apartment_uuid)

    from django.db import transaction

    with transaction.atomic():
        _reset(apartment_uuid, variant, namespace)
        _ensure_single_lottery_event(apartment_uuid)
        existing = _create_customer(variant, namespace, "existing")
        new = _create_customer(variant, namespace, "new")
        _create_existing_reservation(apartment_uuid, existing)

    return {
        "scenario": SCENARIO_NAME,
        "variant": variant,
        "namespace": namespace,
        "project_uuid": apartment["project_uuid"],
        "apartment_uuid": apartment_uuid,
        "apartment_number": apartment["apartment_number"],
        "existing_customer": _customer_data(existing),
        "new_customer": _customer_data(new),
    }
