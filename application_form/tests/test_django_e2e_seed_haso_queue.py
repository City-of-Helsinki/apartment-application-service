import importlib
import json
import sys
import uuid

import pytest

from apartment.tests.factories import ApartmentData
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation, LotteryEvent
from application_form.tests.factories import (
    ApartmentReservationFactory,
    LotteryEventFactory,
)
from customer.models import Customer
from customer.tests.factories import CustomerFactory
from users.models import Profile

# E2E tooling at the repo root; excluded from built images by .dockerignore.
seed_module = pytest.importorskip("django_e2e_seed_haso_queue")
SCENARIOS = seed_module.SCENARIOS
E2E_EMAIL_DOMAIN = seed_module.E2E_EMAIL_DOMAIN
is_e2e_reservation = seed_module.is_e2e_reservation
select_apartments = seed_module.select_apartments
reset_scenario = seed_module.reset_scenario
seed_scenario = seed_module.seed_scenario
main = seed_module.main

ROLES = ("existing", "new")


def _email(scenario, role):
    """
    Return the primary profile email of a scenario's e2e customer.

            Parameters:
                    scenario (str): Scenario name, e.g. "on_time"
                    role (str): "existing" or "new"

            Returns:
                    email (str): The e2e customer's email
    """
    return f"haso-{scenario}-{role}@e2e.invalid"


def _customers_by_email(email):
    """
    Return customers whose primary profile has the given email.

            Parameters:
                    email (str): Primary profile email

            Returns:
                    customers (QuerySet): Matching customers
    """
    return Customer.objects.filter(primary_profile__email=email)


def _apartment(project_uuid, apartment_uuid, ownership_type="HASO", number="A1"):
    """
    Build a stub apartment document as returned by the Drupal search API.

            Parameters:
                    project_uuid (str): Project uuid
                    apartment_uuid (str): Apartment uuid
                    ownership_type (str): project_ownership_type value
                    number (str): Apartment number

            Returns:
                    apartment (ApartmentData): Stub apartment document
    """
    return ApartmentData(
        uuid=apartment_uuid,
        project_uuid=project_uuid,
        project_ownership_type=ownership_type,
        apartment_number=number,
    )


def _project(apartment):
    """
    Build a stub project document from an apartment's project fields.

            Parameters:
                    apartment (ApartmentData): Stub apartment

            Returns:
                    project (ApartmentData): Stub project document
    """
    return ApartmentData(
        project_uuid=apartment.project_uuid,
        project_ownership_type=apartment.project_ownership_type,
    )


@pytest.fixture
def drupal_apartments(monkeypatch):
    """
    Patch the seed module's get_projects/get_apartments with in-memory stubs.

    Returns a function that installs the given stub apartments; no Drupal
    search API calls are made.
    """

    def install(apartments):
        """
        Serve the given stub apartments from the patched queries.

                Parameters:
                        apartments (list[ApartmentData]): Stub apartments
        """

        def get_projects(**filters):
            """Return one stub project per distinct apartment project."""
            projects = {}
            for apartment in apartments:
                projects.setdefault(apartment.project_uuid, _project(apartment))
            return list(projects.values())

        def get_apartments(project_uuid=None, include_project_fields=False, **filters):
            """Return stub apartments, optionally of a single project."""
            if project_uuid is None:
                return list(apartments)
            return [
                apartment
                for apartment in apartments
                if str(apartment.project_uuid) == str(project_uuid)
            ]

        monkeypatch.setattr(seed_module, "get_projects", get_projects)
        monkeypatch.setattr(seed_module, "get_apartments", get_apartments)

    return install


@pytest.fixture
def haso_apartment():
    """
    Return a single stub HASO apartment.
    """
    return _apartment(str(uuid.uuid4()), str(uuid.uuid4()), number="B12")


def _next_positions(apartment_uuid):
    """
    Return unused list and queue positions for a new reservation.

    The factory's fuzzy positions only range over 0..1, which collides with
    the (apartment_uuid, list_position) unique constraint when an apartment
    gets several reservations.

            Parameters:
                    apartment_uuid (str): Apartment of the reservation

            Returns:
                    positions (dict): list_position and queue_position values
    """
    position = (
        ApartmentReservation.objects.filter(apartment_uuid=apartment_uuid).count() + 1
    )
    return {"list_position": position, "queue_position": position}


def _e2e_reservation(apartment_uuid, email):
    """
    Create a reservation whose customer is identified as e2e data.

            Parameters:
                    apartment_uuid (str): Apartment of the reservation
                    email (str): Primary profile email of the customer

            Returns:
                    reservation (ApartmentReservation): The created reservation
    """
    customer = CustomerFactory(primary_profile__email=email)
    return ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        customer=customer,
        application_apartment=None,
        **_next_positions(apartment_uuid),
    )


def _non_e2e_reservation(apartment_uuid, **kwargs):
    """
    Create a reservation for a regular (non-e2e) customer.

            Parameters:
                    apartment_uuid (str): Apartment of the reservation
                    **kwargs: Extra ApartmentReservationFactory fields

            Returns:
                    reservation (ApartmentReservation): The created reservation
    """
    customer = CustomerFactory(primary_profile__email="someone@example.com")
    return ApartmentReservationFactory(
        apartment_uuid=apartment_uuid,
        customer=customer,
        **{**_next_positions(apartment_uuid), **kwargs},
    )


def test_constants():
    """
    - scenarios are on_time and late, in that order
    - e2e customers use the reserved e2e.invalid email domain
    """
    assert SCENARIOS == ("on_time", "late")
    assert E2E_EMAIL_DOMAIN == "e2e.invalid"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email",
    ["haso-on_time-existing@e2e.invalid", "anything@e2e.invalid"],
)
def test_is_e2e_reservation_true_for_e2e_email(email):
    """
    - a reservation whose customer email ends with @e2e.invalid is e2e data
    """
    reservation = _e2e_reservation(str(uuid.uuid4()), email)

    assert is_e2e_reservation(reservation) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email",
    [
        "someone@example.com",
        "someone@e2e.invalid.example.com",
        "someone@note2e.invalid",
        "",
    ],
)
def test_is_e2e_reservation_false_for_other_email(email):
    """
    - a reservation whose customer email does not end with @e2e.invalid is
      not e2e data, including look-alike domains and empty emails
    """
    customer = CustomerFactory(primary_profile__email=email)
    reservation = ApartmentReservationFactory(
        customer=customer, application_apartment=None
    )

    assert is_e2e_reservation(reservation) is False


@pytest.mark.django_db
def test_select_apartments_orders_by_project_and_apartment_uuid(drupal_apartments):
    """
    - apartments are ordered by (project_uuid, apartment uuid) as strings
    - only the requested number of apartments is returned
    """
    project_a = "10000000-0000-0000-0000-000000000000"
    project_b = "20000000-0000-0000-0000-000000000000"
    apartments = [
        _apartment(project_b, "a0000000-0000-0000-0000-000000000000"),
        _apartment(project_a, "c0000000-0000-0000-0000-000000000000"),
        _apartment(project_a, "b0000000-0000-0000-0000-000000000000"),
        _apartment(project_b, "00000000-0000-0000-0000-000000000001"),
    ]
    drupal_apartments(apartments)

    selected = select_apartments(3)

    assert [(str(a.project_uuid), str(a.uuid)) for a in selected] == [
        (project_a, "b0000000-0000-0000-0000-000000000000"),
        (project_a, "c0000000-0000-0000-0000-000000000000"),
        (project_b, "00000000-0000-0000-0000-000000000001"),
    ]


@pytest.mark.django_db
def test_select_apartments_filters_haso_case_insensitively(drupal_apartments):
    """
    - apartments of HASO projects are selected regardless of letter case
    - apartments of Hitas and Puolihitas projects are never selected
    """
    apartments = [
        _apartment("1", "00000000-0000-0000-0000-00000000001a", ownership_type="Hitas"),
        _apartment("2", "00000000-0000-0000-0000-00000000002a", ownership_type="haso"),
        _apartment(
            "3", "00000000-0000-0000-0000-00000000003a", ownership_type="Puolihitas"
        ),
        _apartment("4", "00000000-0000-0000-0000-00000000004a", ownership_type="Haso"),
        _apartment("5", "00000000-0000-0000-0000-00000000005a", ownership_type="HASO"),
    ]
    drupal_apartments(apartments)

    selected = select_apartments(3)

    assert [str(a.uuid) for a in selected] == [
        "00000000-0000-0000-0000-00000000002a",
        "00000000-0000-0000-0000-00000000004a",
        "00000000-0000-0000-0000-00000000005a",
    ]


@pytest.mark.django_db
def test_select_apartments_skips_apartments_with_non_e2e_reservations(
    drupal_apartments,
):
    """
    - an apartment with any non-e2e reservation is skipped
    - an apartment mixing e2e and non-e2e reservations is skipped
    - the next free apartments are selected instead
    """
    apartments = [
        _apartment("1", "00000000-0000-0000-0000-00000000001a"),
        _apartment("1", "00000000-0000-0000-0000-00000000001b"),
        _apartment("2", "00000000-0000-0000-0000-00000000002a"),
        _apartment("2", "00000000-0000-0000-0000-00000000002b"),
    ]
    drupal_apartments(apartments)
    _non_e2e_reservation("00000000-0000-0000-0000-00000000001a")
    _e2e_reservation(
        "00000000-0000-0000-0000-00000000001b", _email("on_time", "existing")
    )
    _non_e2e_reservation("00000000-0000-0000-0000-00000000001b")

    selected = select_apartments(2)

    assert [str(a.uuid) for a in selected] == [
        "00000000-0000-0000-0000-00000000002a",
        "00000000-0000-0000-0000-00000000002b",
    ]


@pytest.mark.django_db
def test_select_apartments_skips_canceled_non_e2e_reservations(drupal_apartments):
    """
    - an apartment with a canceled non-e2e reservation is still skipped
    """
    drupal_apartments(
        [
            _apartment("1", "00000000-0000-0000-0000-00000000001a"),
            _apartment("2", "00000000-0000-0000-0000-00000000002a"),
        ]
    )
    _non_e2e_reservation(
        "00000000-0000-0000-0000-00000000001a", state=ApartmentReservationState.CANCELED
    )

    selected = select_apartments(1)

    assert [str(a.uuid) for a in selected] == ["00000000-0000-0000-0000-00000000002a"]


@pytest.mark.django_db
def test_select_apartments_accepts_apartments_with_only_e2e_reservations(
    drupal_apartments,
):
    """
    - an apartment whose reservations all belong to e2e customers is selected
      so a re-run reuses the apartment of a previous run
    """
    drupal_apartments(
        [
            _apartment("1", "00000000-0000-0000-0000-00000000001a"),
            _apartment("2", "00000000-0000-0000-0000-00000000002a"),
        ]
    )
    _e2e_reservation(
        "00000000-0000-0000-0000-00000000001a", _email("on_time", "existing")
    )
    _e2e_reservation("00000000-0000-0000-0000-00000000001a", _email("on_time", "new"))

    selected = select_apartments(2)

    assert [str(a.uuid) for a in selected] == [
        "00000000-0000-0000-0000-00000000001a",
        "00000000-0000-0000-0000-00000000002a",
    ]


@pytest.mark.django_db
def test_select_apartments_raises_when_too_few_apartments(drupal_apartments):
    """
    - RuntimeError is raised when fewer eligible apartments than requested
      exist
    - ineligible apartments do not count towards the requested number
    """
    drupal_apartments(
        [
            _apartment("1", "00000000-0000-0000-0000-00000000001a"),
            _apartment(
                "2", "00000000-0000-0000-0000-00000000002a", ownership_type="Hitas"
            ),
            _apartment("3", "00000000-0000-0000-0000-00000000003a"),
        ]
    )
    _non_e2e_reservation("00000000-0000-0000-0000-00000000003a")

    with pytest.raises(RuntimeError):
        select_apartments(2)


@pytest.mark.django_db
def test_select_apartments_raises_when_no_apartments(drupal_apartments):
    """
    - RuntimeError is raised when the search API returns no apartments
    """
    drupal_apartments([])

    with pytest.raises(RuntimeError):
        select_apartments(1)


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_seed_scenario_creates_existing_customer_and_reservation(
    scenario, haso_apartment
):
    """
    - the existing customer is created with RoR 500, not old batch
    - the existing customer has one non-late submitted reservation on the
      apartment at queue position 1 and list position 1 with RoR 500
    """
    seed_scenario(scenario, haso_apartment)

    existing = _customers_by_email(_email(scenario, "existing")).get()
    assert existing.right_of_residence == 500
    assert existing.right_of_residence_is_old_batch is False

    reservation = ApartmentReservation.objects.get(customer=existing)
    assert str(reservation.apartment_uuid) == str(haso_apartment.uuid)
    assert reservation.submitted_late is False
    assert reservation.state == ApartmentReservationState.SUBMITTED
    assert reservation.queue_position == 1
    assert reservation.list_position == 1
    assert reservation.right_of_residence == 500
    assert (
        ApartmentReservation.objects.filter(apartment_uuid=haso_apartment.uuid).count()
        == 1
    )


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_seed_scenario_creates_new_customer_without_reservation(
    scenario, haso_apartment
):
    """
    - the new customer is created with RoR 100, not old batch
    - the new customer has no reservations
    """
    seed_scenario(scenario, haso_apartment)

    new = _customers_by_email(_email(scenario, "new")).get()
    assert new.right_of_residence == 100
    assert new.right_of_residence_is_old_batch is False
    assert not ApartmentReservation.objects.filter(customer=new).exists()


@pytest.mark.django_db
def test_seed_scenario_creates_lottery_event(haso_apartment):
    """
    - a lottery event is created for the apartment when none exists
    """
    assert not LotteryEvent.objects.filter(apartment_uuid=haso_apartment.uuid).exists()

    seed_scenario("on_time", haso_apartment)

    assert LotteryEvent.objects.filter(apartment_uuid=haso_apartment.uuid).count() == 1


@pytest.mark.django_db
def test_seed_scenario_reuses_existing_lottery_event(haso_apartment):
    """
    - an existing lottery event of the apartment is reused, not duplicated
    """
    event = LotteryEventFactory(apartment_uuid=haso_apartment.uuid)

    seed_scenario("on_time", haso_apartment)

    events = LotteryEvent.objects.filter(apartment_uuid=haso_apartment.uuid)
    assert list(events) == [event]


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_seed_scenario_returns_dict_matching_db(scenario, haso_apartment):
    """
    - the returned dict has the scenario, project and apartment as strings
    - customer ids and names match the created customers
    - last names are searchable (at least 3 characters) and differ by role
    """
    result = seed_scenario(scenario, haso_apartment)

    assert set(result) == {
        "scenario",
        "project_uuid",
        "apartment_uuid",
        "apartment_number",
        "existing_customer",
        "new_customer",
    }
    assert result["scenario"] == scenario
    assert result["project_uuid"] == str(haso_apartment.project_uuid)
    assert result["apartment_uuid"] == str(haso_apartment.uuid)
    assert result["apartment_number"] == haso_apartment.apartment_number

    for role in ROLES:
        customer = _customers_by_email(_email(scenario, role)).get()
        data = result[f"{role}_customer"]
        assert set(data) == {"id", "first_name", "last_name"}
        assert data["id"] == customer.id
        assert data["first_name"] == customer.primary_profile.first_name
        assert data["last_name"] == customer.primary_profile.last_name
        assert len(data["last_name"]) >= 3

    assert (
        result["existing_customer"]["last_name"] != result["new_customer"]["last_name"]
    )
    json.dumps(result)


@pytest.mark.django_db
def test_seed_scenario_last_names_differ_between_scenarios():
    """
    - every scenario/role pair gets its own last name so a customer search
      in one scenario never matches another scenario's customer
    """
    apartments = [
        _apartment("1", "00000000-0000-0000-0000-00000000001a"),
        _apartment("2", "00000000-0000-0000-0000-00000000002a"),
    ]
    results = [
        seed_scenario(scenario, apartment)
        for scenario, apartment in zip(SCENARIOS, apartments)
    ]

    last_names = [
        result[f"{role}_customer"]["last_name"] for result in results for role in ROLES
    ]
    assert len(set(last_names)) == len(last_names)
    for name in last_names:
        assert all(name not in other for other in last_names if other != name)


@pytest.mark.django_db
def test_seed_scenario_is_idempotent(haso_apartment):
    """
    - re-seeding leaves a single customer per role
    - re-seeding leaves a single reservation on the apartment at queue 1
    - reservations made for the new customer by a previous e2e run are removed
    - the lottery event is not duplicated
    """
    first = seed_scenario("on_time", haso_apartment)
    new_customer = Customer.objects.get(pk=first["new_customer"]["id"])
    # Simulate the e2e run adding the new customer at the front of the queue.
    ApartmentReservation.objects.filter(apartment_uuid=haso_apartment.uuid).update(
        queue_position=2, list_position=2
    )
    ApartmentReservationFactory(
        apartment_uuid=haso_apartment.uuid,
        customer=new_customer,
        application_apartment=None,
        queue_position=1,
        list_position=3,
        submitted_late=False,
    )

    second = seed_scenario("on_time", haso_apartment)

    for role in ROLES:
        assert _customers_by_email(_email("on_time", role)).count() == 1
        assert Profile.objects.filter(email=_email("on_time", role)).count() == 1
    reservations = ApartmentReservation.objects.filter(
        apartment_uuid=haso_apartment.uuid
    )
    assert reservations.count() == 1
    reservation = reservations.get()
    assert reservation.customer_id == second["existing_customer"]["id"]
    assert reservation.queue_position == 1
    assert reservation.list_position == 1
    assert not ApartmentReservation.objects.filter(
        customer_id=second["new_customer"]["id"]
    ).exists()
    assert LotteryEvent.objects.filter(apartment_uuid=haso_apartment.uuid).count() == 1


@pytest.mark.django_db
def test_seed_scenario_does_not_touch_non_e2e_data(haso_apartment):
    """
    - non-e2e customers and reservations on other apartments are untouched
    """
    other = _non_e2e_reservation(str(uuid.uuid4()), queue_position=1)
    other_values = (other.customer_id, other.queue_position, other.state)

    seed_scenario("on_time", haso_apartment)

    other.refresh_from_db()
    assert (other.customer_id, other.queue_position, other.state) == other_values


@pytest.mark.django_db
def test_seed_scenario_rejects_unknown_scenario(haso_apartment):
    """
    - an unknown scenario raises ValueError
    - nothing is created
    """
    customer_count = Customer.objects.count()

    with pytest.raises(ValueError):
        seed_scenario("unknown", haso_apartment)

    assert Customer.objects.count() == customer_count
    assert not ApartmentReservation.objects.filter(
        apartment_uuid=haso_apartment.uuid
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_reset_scenario_removes_e2e_customers_and_reservations(
    scenario, haso_apartment
):
    """
    - the scenario's e2e customers, their profiles and reservations are removed
    """
    result = seed_scenario(scenario, haso_apartment)
    customer_ids = [result[f"{role}_customer"]["id"] for role in ROLES]

    reset_scenario(scenario)

    assert not Customer.objects.filter(pk__in=customer_ids).exists()
    assert not ApartmentReservation.objects.filter(
        customer_id__in=customer_ids
    ).exists()
    for role in ROLES:
        assert not Profile.objects.filter(email=_email(scenario, role)).exists()


@pytest.mark.django_db
def test_reset_scenario_keeps_non_e2e_data(haso_apartment):
    """
    - non-e2e customers and reservations survive a reset, also on the
      scenario's apartment
    """
    seed_scenario("on_time", haso_apartment)
    same_apartment = _non_e2e_reservation(haso_apartment.uuid, queue_position=5)
    other_apartment = _non_e2e_reservation(str(uuid.uuid4()))
    lone_customer = CustomerFactory(primary_profile__email="lone@example.com")

    reset_scenario("on_time")

    assert ApartmentReservation.objects.filter(pk=same_apartment.pk).exists()
    assert ApartmentReservation.objects.filter(pk=other_apartment.pk).exists()
    assert (
        Customer.objects.filter(
            pk__in=[
                same_apartment.customer_id,
                other_apartment.customer_id,
                lone_customer.pk,
            ]
        ).count()
        == 3
    )


@pytest.mark.django_db
def test_reset_scenario_keeps_other_scenario():
    """
    - resetting one scenario leaves the other scenario's data intact
    """
    on_time_apartment = _apartment("1", "00000000-0000-0000-0000-00000000001a")
    late_apartment = _apartment("2", "00000000-0000-0000-0000-00000000002a")
    seed_scenario("on_time", on_time_apartment)
    late = seed_scenario("late", late_apartment)

    reset_scenario("on_time")

    for role in ROLES:
        assert not _customers_by_email(_email("on_time", role)).exists()
        assert _customers_by_email(_email("late", role)).count() == 1
    assert ApartmentReservation.objects.filter(
        customer_id=late["existing_customer"]["id"], queue_position=1
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_reset_scenario_is_idempotent(scenario):
    """
    - resetting when nothing has been seeded does not raise
    - resetting twice does not raise
    """
    customer_count = Customer.objects.count()

    reset_scenario(scenario)
    reset_scenario(scenario)

    assert Customer.objects.count() == customer_count


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", ["unknown", "", "ON_TIME", "on-time"])
def test_reset_scenario_rejects_unknown_scenario(scenario):
    """
    - an unknown scenario raises ValueError
    """
    with pytest.raises(ValueError):
        reset_scenario(scenario)


@pytest.mark.django_db
def test_main_seeds_every_scenario_and_prints_json(drupal_apartments, capsys):
    """
    - main returns exit code 0
    - stdout is JSON keyed by scenario
    - each scenario is seeded on its own apartment, in selection order
    - the printed data matches the database
    """
    apartments = [
        _apartment("1", "00000000-0000-0000-0000-00000000001a", number="A1"),
        _apartment("2", "00000000-0000-0000-0000-00000000002a", number="A2"),
        _apartment("3", "00000000-0000-0000-0000-00000000003a", number="A3"),
    ]
    drupal_apartments(apartments)

    exit_code = main([])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert set(output) == set(SCENARIOS)
    assert output["on_time"]["apartment_uuid"] == "00000000-0000-0000-0000-00000000001a"
    assert output["late"]["apartment_uuid"] == "00000000-0000-0000-0000-00000000002a"
    for scenario in SCENARIOS:
        data = output[scenario]
        assert data["scenario"] == scenario
        for role in ROLES:
            customer = _customers_by_email(_email(scenario, role)).get()
            assert data[f"{role}_customer"]["id"] == customer.id
        assert ApartmentReservation.objects.filter(
            apartment_uuid=data["apartment_uuid"],
            customer_id=data["existing_customer"]["id"],
            queue_position=1,
        ).exists()
    assert not ApartmentReservation.objects.filter(
        apartment_uuid="00000000-0000-0000-0000-00000000003a"
    ).exists()


@pytest.mark.django_db
def test_main_is_repeatable(drupal_apartments, capsys):
    """
    - running main twice reuses the same apartments (only e2e reservations)
    - no customers are duplicated
    """
    drupal_apartments(
        [
            _apartment("1", "00000000-0000-0000-0000-00000000001a"),
            _apartment("2", "00000000-0000-0000-0000-00000000002a"),
        ]
    )

    assert main([]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main([]) == 0
    second = json.loads(capsys.readouterr().out)

    for scenario in SCENARIOS:
        assert first[scenario]["apartment_uuid"] == second[scenario]["apartment_uuid"]
        for role in ROLES:
            assert _customers_by_email(_email(scenario, role)).count() == 1


@pytest.mark.django_db
def test_main_defaults_to_sys_argv(drupal_apartments, monkeypatch, capsys):
    """
    - main reads arguments from sys.argv[1:] when argv is None
    """
    drupal_apartments(
        [
            _apartment("1", "00000000-0000-0000-0000-00000000001a"),
            _apartment("2", "00000000-0000-0000-0000-00000000002a"),
        ]
    )
    monkeypatch.setattr(sys, "argv", ["django_e2e_seed_haso_queue.py"])

    exit_code = main()

    assert exit_code == 0
    assert set(json.loads(capsys.readouterr().out)) == set(SCENARIOS)


@pytest.mark.django_db
@pytest.mark.parametrize("argv", [["on_time"], ["a", "b"], ["--help"]])
def test_main_rejects_arguments(argv, drupal_apartments, capsys):
    """
    - main returns exit code 2 when given any arguments
    - usage is printed to stderr
    - nothing is seeded
    """
    drupal_apartments(
        [
            _apartment("1", "00000000-0000-0000-0000-00000000001a"),
            _apartment("2", "00000000-0000-0000-0000-00000000002a"),
        ]
    )
    customer_count = Customer.objects.count()

    exit_code = main(argv)

    assert exit_code == 2
    assert "Usage" in capsys.readouterr().err
    assert Customer.objects.count() == customer_count


@pytest.mark.django_db
def test_main_returns_1_when_not_enough_apartments(drupal_apartments, capsys):
    """
    - main returns exit code 1 when too few eligible apartments exist
    - an error is printed to stderr and nothing to stdout
    - nothing is seeded
    """
    drupal_apartments([_apartment("1", "00000000-0000-0000-0000-00000000001a")])
    customer_count = Customer.objects.count()

    exit_code = main([])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert captured.out.strip() == ""
    assert Customer.objects.count() == customer_count


def test_import_has_no_side_effects(monkeypatch):
    """
    - importing the module does not read sys.argv or touch the database
    - pytest --doctest-modules imports the module with pytest's own argv
    """
    monkeypatch.setattr(sys, "argv", ["pytest", "-ra", "-vvv"])

    importlib.reload(seed_module)
