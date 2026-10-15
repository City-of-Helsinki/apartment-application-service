import importlib
import sys
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from users.enums import Roles
from users.tests.factories import UserFactory

# E2E tooling at the repo root; excluded from built images by .dockerignore.
django_e2e_seed_salesperson = pytest.importorskip("django_e2e_seed_salesperson")
ensure_salesperson = django_e2e_seed_salesperson.ensure_salesperson
main = django_e2e_seed_salesperson.main

User = get_user_model()

SALESPERSON_UUID = "8a5d3c1e-2f4b-4c6d-9e8f-0a1b2c3d4e5f"


def _salesperson_group():
    """
    Return the django_salesperson group created by migrations.

            Returns:
                    group (Group): The django_salesperson group
    """
    return Group.objects.get(name__iexact=Roles.DJANGO_SALESPERSON.name)


@pytest.mark.django_db
def test_ensure_salesperson_creates_user_in_group():
    """
    - a user with the given uuid is created when none exists
    - the user is added to the django_salesperson group
    - the created user is returned
    """
    assert not User.objects.filter(uuid=SALESPERSON_UUID).exists()

    user = ensure_salesperson(SALESPERSON_UUID)

    assert isinstance(user, User)
    assert str(user.uuid) == SALESPERSON_UUID
    assert User.objects.filter(uuid=SALESPERSON_UUID).count() == 1
    assert _salesperson_group().user_set.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_ensure_salesperson_passes_is_django_salesperson():
    """
    - the seeded user is recognised as a Django salesperson
    """
    user = ensure_salesperson(SALESPERSON_UUID)

    user.refresh_from_db()
    assert user.is_django_salesperson()


@pytest.mark.django_db
def test_ensure_salesperson_reuses_existing_user():
    """
    - an existing user with the given uuid is reused, not duplicated
    - the existing user gains the django_salesperson group
    """
    existing = UserFactory(uuid=uuid.UUID(SALESPERSON_UUID))
    assert not existing.is_django_salesperson()
    user_count = User.objects.count()

    user = ensure_salesperson(SALESPERSON_UUID)

    assert user.pk == existing.pk
    assert User.objects.count() == user_count
    existing.refresh_from_db()
    assert existing.is_django_salesperson()


@pytest.mark.django_db
def test_ensure_salesperson_is_idempotent():
    """
    - calling twice yields a single user
    - the user has a single django_salesperson group membership
    """
    first = ensure_salesperson(SALESPERSON_UUID)
    second = ensure_salesperson(SALESPERSON_UUID)

    assert first.pk == second.pk
    assert User.objects.filter(uuid=SALESPERSON_UUID).count() == 1
    assert second.groups.filter(name__iexact=Roles.DJANGO_SALESPERSON.name).count() == 1


@pytest.mark.django_db
def test_ensure_salesperson_does_not_affect_other_users():
    """
    - other users are not added to the django_salesperson group
    """
    other = UserFactory()

    ensure_salesperson(SALESPERSON_UUID)

    other.refresh_from_db()
    assert not other.is_django_salesperson()


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["not-a-uuid", "", "1234", "8a5d3c1e-2f4b"])
def test_ensure_salesperson_rejects_invalid_uuid(value):
    """
    - a value that is not a valid UUID raises ValueError
    - no user is created
    """
    user_count = User.objects.count()

    with pytest.raises(ValueError):
        ensure_salesperson(value)

    assert User.objects.count() == user_count


@pytest.mark.django_db
def test_main_seeds_salesperson():
    """
    - main returns exit code 0 for a single valid uuid
    - the user is created and is a Django salesperson
    """
    exit_code = main([SALESPERSON_UUID])

    assert exit_code == 0
    user = User.objects.get(uuid=SALESPERSON_UUID)
    assert user.is_django_salesperson()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "argv", [[], [SALESPERSON_UUID, SALESPERSON_UUID], ["a", "b", "c"]]
)
def test_main_rejects_wrong_argument_count(argv, capsys):
    """
    - main returns exit code 2 when not given exactly one argument
    - usage is printed to stderr
    - no user is created
    """
    user_count = User.objects.count()

    exit_code = main(argv)

    assert exit_code == 2
    assert "Usage" in capsys.readouterr().err
    assert User.objects.count() == user_count


@pytest.mark.django_db
def test_main_rejects_invalid_uuid(capsys):
    """
    - main returns exit code 2 for a value that is not a valid UUID
    - an error is printed to stderr
    - no user is created
    """
    user_count = User.objects.count()

    exit_code = main(["not-a-uuid"])

    assert exit_code == 2
    assert capsys.readouterr().err.strip() != ""
    assert User.objects.count() == user_count


@pytest.mark.django_db
def test_main_defaults_to_sys_argv(monkeypatch):
    """
    - main reads arguments from sys.argv[1:] when argv is None
    """
    monkeypatch.setattr(
        sys, "argv", ["django_e2e_seed_salesperson.py", SALESPERSON_UUID]
    )

    exit_code = main()

    assert exit_code == 0
    assert User.objects.get(uuid=SALESPERSON_UUID).is_django_salesperson()


def test_import_has_no_side_effects(monkeypatch):
    """
    - importing the module does not read sys.argv or touch the database
    - pytest --doctest-modules imports the module with pytest's own argv
    """
    monkeypatch.setattr(sys, "argv", ["pytest", "-ra", "-vvv"])

    importlib.reload(django_e2e_seed_salesperson)
