import json
import uuid
from pathlib import Path

import pytest

from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation, LotteryEvent, Offer
from application_form.tests.factories import (
    ApartmentReservationFactory,
    LotteryEventFactory,
    OfferFactory,
)
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from e2e.scenarios import haso_queue
from e2e.scenarios.baseline import Baseline, load_baseline
from e2e.scenarios.registry import get_scenario, scenario_names, ScenarioParamsError

# E2E tooling at the repo root; not part of built images, so skip when absent.
BASELINE_PATH = (
    Path(__file__).resolve().parents[3] / "e2e" / "fixtures" / "baseline.json"
)
if not BASELINE_PATH.is_file():
    pytest.skip(
        f"E2E baseline fixture not found at {BASELINE_PATH}",
        allow_module_level=True,
    )

SCENARIO_NAME = "haso_queue"
VARIANTS = ("on_time", "late")
EXPECTED_VARIANT_APARTMENTS = {"on_time": "haso-a1", "late": "haso-a2"}
HASO_APARTMENT_KEYS = ("haso-a1", "haso-a2", "haso-a3", "haso-a4")
MANIFEST_KEYS = {
    "scenario",
    "variant",
    "namespace",
    "project_uuid",
    "apartment_uuid",
    "apartment_number",
    "existing_customer",
    "new_customer",
}
CUSTOMER_KEYS = {"id", "first_name", "last_name"}
ROLES = ("existing", "new")


@pytest.fixture(autouse=True)
def committed_baseline(monkeypatch):
    """
    Point E2E_BASELINE_FILE at the committed baseline file.

            Parameters:
                    monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setenv("E2E_BASELINE_FILE", str(BASELINE_PATH))


@pytest.fixture(scope="module")
def baseline():
    """
    Return the committed baseline.

            Returns:
                    baseline (Baseline): Loaded baseline
    """
    return load_baseline(BASELINE_PATH)


@pytest.fixture
def namespace():
    """
    Return a namespace unique to the test.

            Returns:
                    namespace (str): Value matching ^[a-z0-9-]{1,40}$
    """
    return f"t-{uuid.uuid4().hex[:8]}"


def _seed(variant="on_time", namespace="test-ns", **extra):
    """
    Run the registered haso_queue scenario.

            Parameters:
                    variant (str): Scenario variant
                    namespace (str): Scenario namespace
                    **extra: Additional params (e.g. apartment_key)

            Returns:
                    manifest (dict): Scenario manifest
    """
    return get_scenario(SCENARIO_NAME)(
        {"variant": variant, "namespace": namespace, **extra}
    )


def _reservations(apartment_uuid):
    """
    Return all reservations of an apartment.

            Parameters:
                    apartment_uuid (str): Apartment uuid

            Returns:
                    reservations (QuerySet): Reservations of the apartment
    """
    return ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid)


def _reservation(apartment_uuid, position, **kwargs):
    """
    Create a reservation with explicit unique positions.

    The factory's fuzzy positions collide with the (apartment_uuid,
    list_position) unique constraint, so positions are always given.

            Parameters:
                    apartment_uuid (str): Apartment uuid
                    position (int): list_position and queue_position value
                    **kwargs: Extra ApartmentReservationFactory fields

            Returns:
                    reservation (ApartmentReservation): Created reservation
    """
    fields = {
        "apartment_uuid": apartment_uuid,
        "list_position": position,
        "queue_position": position,
        "application_apartment": None,
        **kwargs,
    }
    return ApartmentReservationFactory(**fields)


def _db_counts():
    """
    Return row counts of the tables the scenario writes to.

            Returns:
                    counts (tuple): (customers, reservations, lottery events)
    """
    return (
        Customer.objects.count(),
        ApartmentReservation.objects.count(),
        LotteryEvent.objects.count(),
    )


def test_scenario_is_registered():
    """
    - importing e2e.scenarios registers "haso_queue"
    - the registered entry is callable
    """
    assert SCENARIO_NAME in scenario_names()
    assert callable(get_scenario(SCENARIO_NAME))


def test_variant_apartments_constant():
    """
    - on_time maps to baseline apartment haso-a1, late to haso-a2
    """
    assert haso_queue.VARIANT_APARTMENTS == EXPECTED_VARIANT_APARTMENTS


def test_variant_apartments_exist_in_baseline(baseline):
    """
    - every variant apartment is a HASO apartment of the committed baseline
    """
    for key in haso_queue.VARIANT_APARTMENTS.values():
        apartment = baseline.apartment(key)
        assert baseline.project(apartment["project_key"])["ownership_type"] == "HASO"


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_manifest_shape(variant, namespace):
    """
    - the manifest has exactly the documented keys
    - customers have id, first_name and last_name
    - uuids are strings and the manifest is JSON serializable
    """
    manifest = _seed(variant, namespace)

    assert set(manifest) == MANIFEST_KEYS
    assert manifest["scenario"] == SCENARIO_NAME
    assert manifest["variant"] == variant
    assert manifest["namespace"] == namespace
    assert isinstance(manifest["project_uuid"], str)
    assert isinstance(manifest["apartment_uuid"], str)
    for role in ROLES:
        customer = manifest[f"{role}_customer"]
        assert set(customer) == CUSTOMER_KEYS
        assert isinstance(customer["id"], int)
    assert json.loads(json.dumps(manifest)) == manifest


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_selects_baseline_apartment(variant, namespace, baseline):
    """
    - the manifest apartment is the baseline apartment mapped to the variant
    - project uuid and apartment number come from the baseline
    """
    expected = baseline.apartment(EXPECTED_VARIANT_APARTMENTS[variant])

    manifest = _seed(variant, namespace)

    assert manifest["apartment_uuid"] == expected["uuid"]
    assert manifest["project_uuid"] == expected["project_uuid"]
    assert manifest["apartment_number"] == expected["apartment_number"]


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_manifest_customers_match_database(variant, namespace):
    """
    - customer ids exist and names equal their primary profile names
    """
    manifest = _seed(variant, namespace)

    for role in ROLES:
        data = manifest[f"{role}_customer"]
        customer = Customer.objects.select_related("primary_profile").get(pk=data["id"])
        assert customer.primary_profile.first_name == data["first_name"]
        assert customer.primary_profile.last_name == data["last_name"]


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_existing_customer_and_reservation(variant, namespace):
    """
    - the existing customer has RoR 500 and is not old batch
    - the apartment has exactly one reservation, owned by the existing customer
    - it is SUBMITTED, not late, queue and list position 1, RoR 500
    """
    manifest = _seed(variant, namespace)

    existing = Customer.objects.get(pk=manifest["existing_customer"]["id"])
    assert existing.right_of_residence == 500
    assert existing.right_of_residence_is_old_batch is False

    reservation = _reservations(manifest["apartment_uuid"]).get()
    assert reservation.customer_id == existing.pk
    assert reservation.state == ApartmentReservationState.SUBMITTED
    assert reservation.submitted_late is False
    assert reservation.queue_position == 1
    assert reservation.list_position == 1
    assert reservation.right_of_residence == 500
    assert reservation.right_of_residence_is_old_batch is False


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_new_customer_has_no_reservation(variant, namespace):
    """
    - the new customer has RoR 100 and is not old batch
    - the new customer has no reservations at all
    """
    manifest = _seed(variant, namespace)

    new = Customer.objects.get(pk=manifest["new_customer"]["id"])
    assert new.right_of_residence == 100
    assert new.right_of_residence_is_old_batch is False
    assert not ApartmentReservation.objects.filter(customer=new).exists()


@pytest.mark.django_db
def test_lottery_event_created_once_over_repeated_runs(namespace):
    """
    - a lottery event exists for the apartment after seeding
    - repeated runs keep exactly one lottery event
    """
    for _ in range(3):
        manifest = _seed("on_time", namespace)

    assert (
        LotteryEvent.objects.filter(apartment_uuid=manifest["apartment_uuid"]).count()
        == 1
    )


@pytest.mark.django_db
def test_lottery_event_existing_is_kept_single(baseline, namespace):
    """
    - a pre-existing lottery event does not lead to a second one
    """
    apartment_uuid = baseline.apartment("haso-a1")["uuid"]
    LotteryEventFactory(apartment_uuid=apartment_uuid)

    _seed("on_time", namespace)

    assert LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).count() == 1


@pytest.mark.django_db
def test_lottery_event_duplicates_collapse_to_one(baseline, namespace):
    """
    - duplicate lottery events of the apartment are reduced to exactly one
    """
    apartment_uuid = baseline.apartment("haso-a1")["uuid"]
    LotteryEventFactory(apartment_uuid=apartment_uuid)
    LotteryEventFactory(apartment_uuid=apartment_uuid)

    _seed("on_time", namespace)

    assert LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).count() == 1


@pytest.mark.django_db
def test_reseed_keeps_only_newest_existing_reservation(namespace):
    """
    - re-running leaves a single reservation on the apartment
    - it belongs to the newest run's existing customer at queue position 1
    """
    _seed("on_time", namespace)
    second = _seed("on_time", namespace)

    reservation = _reservations(second["apartment_uuid"]).get()
    assert reservation.customer_id == second["existing_customer"]["id"]
    assert reservation.queue_position == 1
    assert reservation.list_position == 1


@pytest.mark.django_db
def test_reseed_deletes_reservations_added_afterwards(namespace):
    """
    - reservations added to the apartment after seeding (e.g. by the UI)
      are deleted on reseed, including their dependent offer rows
    - the previous run's new customer has no reservations left
    """
    first = _seed("on_time", namespace)
    new_customer = Customer.objects.get(pk=first["new_customer"]["id"])
    added = _reservation(
        first["apartment_uuid"],
        2,
        customer=new_customer,
        state=ApartmentReservationState.SUBMITTED,
        submitted_late=False,
    )
    OfferFactory(apartment_reservation=added)

    second = _seed("on_time", namespace)

    assert not ApartmentReservation.objects.filter(pk=added.pk).exists()
    assert not Offer.objects.filter(apartment_reservation_id=added.pk).exists()
    assert not ApartmentReservation.objects.filter(customer=new_customer).exists()
    assert list(
        _reservations(second["apartment_uuid"]).values_list("customer_id", flat=True)
    ) == [second["existing_customer"]["id"]]


@pytest.mark.django_db
def test_reseed_deletes_foreign_reservations_on_apartment(baseline, namespace):
    """
    - any reservation on the scenario apartment is deleted, whoever owns it
    - the owning non-scenario customer itself is kept
    """
    apartment_uuid = baseline.apartment("haso-a1")["uuid"]
    foreign = _reservation(apartment_uuid, 7, customer=CustomerFactory())

    manifest = _seed("on_time", namespace)

    assert not ApartmentReservation.objects.filter(pk=foreign.pk).exists()
    assert Customer.objects.filter(pk=foreign.customer_id).exists()
    assert _reservations(apartment_uuid).get().customer_id == (
        manifest["existing_customer"]["id"]
    )


@pytest.mark.django_db
def test_reseed_same_namespace_keeps_names_unique(namespace):
    """
    - after re-running in the same namespace each manifest last name matches
      exactly one customer
    """
    _seed("on_time", namespace)
    second = _seed("on_time", namespace)

    for role in ROLES:
        last_name = second[f"{role}_customer"]["last_name"]
        assert (
            Customer.objects.filter(primary_profile__last_name=last_name).count() == 1
        )


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_customer_name_rules(variant, namespace):
    """
    - last names are at least 3 characters long
    - last names embed the namespace
    - neither last name contains the other
    """
    manifest = _seed(variant, namespace)

    existing = manifest["existing_customer"]["last_name"]
    new = manifest["new_customer"]["last_name"]
    for last_name in (existing, new):
        assert len(last_name) >= 3
        assert namespace in last_name.lower()
    assert existing not in new
    assert new not in existing


@pytest.mark.django_db
def test_namespaces_produce_distinct_names():
    """
    - different namespaces yield different last names for both roles
    """
    first = _seed("on_time", "ns-alpha")
    second = _seed("late", "ns-beta")

    names = [
        manifest[f"{role}_customer"]["last_name"]
        for manifest in (first, second)
        for role in ROLES
    ]
    assert len(set(names)) == len(names)


@pytest.mark.django_db
def test_other_namespace_customers_are_untouched():
    """
    - seeding the same apartment in another namespace keeps the first
      namespace's customers and their profile names
    """
    first = _seed("on_time", "ns-alpha")

    second = _seed("on_time", "ns-beta")

    for role in ROLES:
        data = first[f"{role}_customer"]
        customer = Customer.objects.select_related("primary_profile").get(pk=data["id"])
        assert customer.primary_profile.last_name == data["last_name"]
    assert _reservations(second["apartment_uuid"]).get().customer_id == (
        second["existing_customer"]["id"]
    )


@pytest.mark.django_db
def test_other_namespace_reservation_on_other_apartment_untouched():
    """
    - a namespace's reservation on another variant apartment survives seeding
      a different variant in another namespace
    """
    late = _seed("late", "ns-alpha")

    _seed("on_time", "ns-beta")

    reservation = _reservations(late["apartment_uuid"]).get()
    assert reservation.customer_id == late["existing_customer"]["id"]


@pytest.mark.django_db
def test_reservations_on_other_apartments_untouched(baseline, namespace):
    """
    - reservations on non-e2e apartments are untouched
    - reservations on other baseline apartments are untouched
    """
    other = _reservation(str(uuid.uuid4()), 1)
    spare = _reservation(baseline.apartment("haso-a3")["uuid"], 1)
    snapshots = {
        reservation.pk: (
            reservation.customer_id,
            reservation.queue_position,
            reservation.list_position,
            reservation.state,
        )
        for reservation in (other, spare)
    }

    _seed("on_time", namespace)

    for reservation in (other, spare):
        reservation.refresh_from_db()
        assert snapshots[reservation.pk] == (
            reservation.customer_id,
            reservation.queue_position,
            reservation.list_position,
            reservation.state,
        )


@pytest.mark.django_db
@pytest.mark.parametrize("apartment_key", HASO_APARTMENT_KEYS)
@pytest.mark.parametrize("variant", VARIANTS)
def test_apartment_key_overrides_variant_apartment(
    variant, apartment_key, namespace, baseline
):
    """
    - an allowed apartment_key selects that baseline apartment
    - the variant is still reported in the manifest
    """
    expected = baseline.apartment(apartment_key)

    manifest = _seed(variant, namespace, apartment_key=apartment_key)

    assert manifest["variant"] == variant
    assert manifest["apartment_uuid"] == expected["uuid"]
    assert manifest["apartment_number"] == expected["apartment_number"]
    assert manifest["project_uuid"] == expected["project_uuid"]
    assert _reservations(expected["uuid"]).get().customer_id == (
        manifest["existing_customer"]["id"]
    )


@pytest.mark.django_db
def test_apartment_key_leaves_default_apartment_untouched(baseline, namespace):
    """
    - seeding with apartment_key haso-a3 does not reset the variant's default
      apartment haso-a1
    """
    default = _seed("on_time", "ns-default")

    _seed("on_time", namespace, apartment_key="haso-a3")

    reservation = _reservations(default["apartment_uuid"]).get()
    assert reservation.customer_id == default["existing_customer"]["id"]


INVALID_PARAMS = [
    pytest.param(None, id="none"),
    pytest.param([], id="list"),
    pytest.param("on_time", id="string"),
    pytest.param({}, id="empty"),
    pytest.param({"namespace": "ns"}, id="variant-missing"),
    pytest.param({"variant": "on_time"}, id="namespace-missing"),
    pytest.param({"variant": "early", "namespace": "ns"}, id="variant-unknown"),
    pytest.param({"variant": "ON_TIME", "namespace": "ns"}, id="variant-case"),
    pytest.param({"variant": "", "namespace": "ns"}, id="variant-empty"),
    pytest.param({"variant": None, "namespace": "ns"}, id="variant-null"),
    pytest.param({"variant": 1, "namespace": "ns"}, id="variant-int"),
    pytest.param({"variant": ["on_time"], "namespace": "ns"}, id="variant-list"),
    pytest.param({"variant": "on_time", "namespace": ""}, id="namespace-empty"),
    pytest.param({"variant": "on_time", "namespace": "Ns"}, id="namespace-upper"),
    pytest.param({"variant": "on_time", "namespace": "n s"}, id="namespace-whitespace"),
    pytest.param({"variant": "on_time", "namespace": "n_s"}, id="namespace-underscore"),
    pytest.param(
        {"variant": "on_time", "namespace": "../ns"}, id="namespace-path-traversal"
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns%"}, id="namespace-sql-wildcard"
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns\n"}, id="namespace-trailing-newline"
    ),
    pytest.param({"variant": "on_time", "namespace": "ä"}, id="namespace-non-ascii"),
    pytest.param(
        {"variant": "on_time", "namespace": "a" * 41}, id="namespace-too-long"
    ),
    pytest.param({"variant": "on_time", "namespace": 12}, id="namespace-int"),
    pytest.param({"variant": "on_time", "namespace": None}, id="namespace-null"),
    pytest.param({"variant": "on_time", "namespace": "ns", "extra": 1}, id="extra-key"),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_uuid": "x"},
        id="extra-key-apartment-uuid",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": "hitas-b1"},
        id="apartment-key-not-haso",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": "haso-a5"},
        id="apartment-key-unknown",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": "haso"},
        id="apartment-key-project-key",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": "HASO-A1"},
        id="apartment-key-case",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": ""},
        id="apartment-key-empty",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": None},
        id="apartment-key-null",
    ),
    pytest.param(
        {"variant": "on_time", "namespace": "ns", "apartment_key": 1},
        id="apartment-key-int",
    ),
]


@pytest.mark.parametrize("params", INVALID_PARAMS)
def test_invalid_params_raise_before_database_access(params):
    """
    - invalid params raise ScenarioParamsError
    - validation happens before any database access (no django_db mark)
    """
    with pytest.raises(ScenarioParamsError):
        get_scenario(SCENARIO_NAME)(params)


@pytest.mark.django_db
@pytest.mark.parametrize("params", INVALID_PARAMS[:8])
def test_invalid_params_write_nothing(params):
    """
    - rejected params leave the database unchanged
    """
    before = _db_counts()

    with pytest.raises(ScenarioParamsError):
        get_scenario(SCENARIO_NAME)(params)

    assert _db_counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize("namespace_value", ["a", "a" * 40, "w0-1a2b3c", "0-9"])
def test_valid_namespace_patterns_are_accepted(namespace_value):
    """
    - namespaces of 1 to 40 chars of [a-z0-9-] are accepted
    """
    manifest = _seed("on_time", namespace_value)

    assert manifest["namespace"] == namespace_value


@pytest.fixture
def non_e2e_apartment(monkeypatch):
    """
    Make Baseline.apartment resolve every key to a uuid without "e2e0".

            Parameters:
                    monkeypatch: pytest monkeypatch fixture

            Returns:
                    apartment_uuid (str): The non-e2e uuid returned for all keys
    """
    apartment_uuid = "00000000-0000-4000-8000-000000000101"
    original = Baseline.apartment

    def apartment(self, key):
        """
        Return the real apartment with its uuid replaced.

                Parameters:
                        key (str): Apartment key

                Returns:
                        apartment (dict): Apartment with a non-e2e uuid
        """
        return {**original(self, key), "uuid": apartment_uuid}

    monkeypatch.setattr(Baseline, "apartment", apartment)
    return apartment_uuid


@pytest.mark.django_db
@pytest.mark.parametrize("variant", VARIANTS)
def test_guard_refuses_non_e2e_apartment(variant, namespace, non_e2e_apartment):
    """
    - an apartment uuid without the "e2e0" prefix raises RuntimeError
    - nothing is written and existing reservations on it survive
    """
    existing = _reservation(non_e2e_apartment, 1)
    before = _db_counts()

    with pytest.raises(RuntimeError):
        _seed(variant, namespace)

    assert _db_counts() == before
    assert ApartmentReservation.objects.filter(pk=existing.pk).exists()
    assert not LotteryEvent.objects.filter(apartment_uuid=non_e2e_apartment).exists()


@pytest.mark.django_db
def test_guard_applies_to_apartment_key(namespace, non_e2e_apartment):
    """
    - the guard also applies when the apartment comes from apartment_key
    """
    before = _db_counts()

    with pytest.raises(RuntimeError):
        _seed("on_time", namespace, apartment_key="haso-a3")

    assert _db_counts() == before


@pytest.mark.django_db
def test_does_not_call_drupal(namespace, monkeypatch):
    """
    - seeding reads apartment data from the baseline, not the search API
    """
    from apartment.elastic import queries

    def fail(*args, **kwargs):
        """Fail the test if the Drupal search API is queried."""
        raise AssertionError("Drupal search API must not be queried")

    monkeypatch.setattr(queries, "get_apartments", fail)
    monkeypatch.setattr(queries, "get_projects", fail)
    monkeypatch.setattr(queries, "get_apartment", fail, raising=False)
    monkeypatch.setattr(queries, "get_project", fail, raising=False)

    manifest = _seed("on_time", namespace)

    assert manifest["scenario"] == SCENARIO_NAME
