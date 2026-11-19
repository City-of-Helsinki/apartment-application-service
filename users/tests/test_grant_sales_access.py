import uuid
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command, CommandError
from helusers.models import ADGroup, ADGroupMapping
from helusers.utils import uuid_to_username
from rest_framework.test import APIRequestFactory

from users.enums import Roles
from users.permissions import IsDjangoSalesperson, IsDrupalSalesperson
from users.services.sales_access import grant_sales_access
from users.tests.factories import UserFactory

User = get_user_model()

USER_UUID = "3f2b1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
OTHER_USER_UUID = "9c8b7a6d-5e4f-4321-8fed-cba987654321"
INVALID_UUIDS = ["not-a-uuid", "", "1234", "3f2b1c4d-5e6f"]


def _group(role):
    """
    Return the group created by migrations for the given role.

            Parameters:
                    role (Roles): The role whose group is returned

            Returns:
                    group (Group): The group matching the role name
    """
    return Group.objects.get(name__iexact=role.name)


def _staff_membership_count(user):
    """
    Return the number of staff group memberships of the user.

            Parameters:
                    user (User): The user to inspect

            Returns:
                    count (int): Number of staff group memberships
    """
    return user.groups.filter(name__iexact=Roles.STAFF.name).count()


def _request_for(user):
    """
    Build a GET request authenticated as the given user.

            Parameters:
                    user (User): The user attached to the request

            Returns:
                    request (WSGIRequest): Request with request.user set
    """
    request = APIRequestFactory().get("/")
    request.user = user
    return request


@pytest.mark.django_db
def test_grant_sales_access_creates_user():
    """
    - a user with the given uuid is created when none exists
    - the username is derived from the uuid with helusers uuid_to_username
    - the created user is returned
    - the user is added to the staff group
    """
    assert not User.objects.filter(uuid=USER_UUID).exists()

    user = grant_sales_access(USER_UUID)

    assert isinstance(user, User)
    assert str(user.uuid) == USER_UUID
    assert user.username == uuid_to_username(USER_UUID)
    assert User.objects.filter(uuid=USER_UUID).count() == 1
    assert _group(Roles.STAFF).user_set.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_grant_sales_access_reuses_existing_user():
    """
    - an existing user with the given uuid is reused, not duplicated
    - the existing username is not changed
    - the existing user gains the staff group
    """
    existing = UserFactory(uuid=uuid.UUID(USER_UUID), username="existing-user")
    assert not existing.is_staff_user()
    user_count = User.objects.count()

    user = grant_sales_access(USER_UUID)

    assert user.pk == existing.pk
    assert User.objects.count() == user_count
    existing.refresh_from_db()
    assert existing.username == "existing-user"
    assert existing.is_staff_user()


@pytest.mark.django_db
def test_grant_sales_access_is_idempotent():
    """
    - calling twice yields a single user
    - the user has a single staff group membership
    """
    first = grant_sales_access(USER_UUID)
    second = grant_sales_access(USER_UUID)

    assert first.pk == second.pk
    assert User.objects.filter(uuid=USER_UUID).count() == 1
    assert _staff_membership_count(second) == 1


@pytest.mark.django_db
def test_grant_sales_access_keeps_existing_groups():
    """
    - groups the user already belongs to are kept
    - the staff group is added alongside them
    """
    existing = UserFactory(uuid=uuid.UUID(USER_UUID))
    _group(Roles.DRUPAL_SALESPERSON).user_set.add(existing)

    user = grant_sales_access(USER_UUID)

    user.refresh_from_db()
    assert user.is_drupal_salesperson()
    assert user.is_staff_user()


@pytest.mark.django_db
def test_grant_sales_access_does_not_affect_other_users():
    """
    - other users are not added to the staff group
    - other users keep their existing groups
    """
    other = UserFactory()
    _group(Roles.DJANGO_SALESPERSON).user_set.add(other)

    grant_sales_access(USER_UUID)

    other.refresh_from_db()
    assert not other.is_staff_user()
    assert other.is_django_salesperson()


@pytest.mark.django_db
@pytest.mark.parametrize("value", INVALID_UUIDS)
def test_grant_sales_access_rejects_invalid_uuid(value):
    """
    - a value that is not a valid UUID raises ValueError
    - no user is created
    - no staff group membership is created
    """
    user_count = User.objects.count()
    staff_count = _group(Roles.STAFF).user_set.count()

    with pytest.raises(ValueError):
        grant_sales_access(value)

    assert User.objects.count() == user_count
    assert _group(Roles.STAFF).user_set.count() == staff_count


@pytest.mark.django_db
def test_grant_sales_access_user_passes_sales_permissions():
    """
    - the resulting user is recognised as a staff user
    - IsDjangoSalesperson grants permission to the user
    - IsDrupalSalesperson grants permission to the user
    """
    user = grant_sales_access(USER_UUID)
    user.refresh_from_db()
    request = _request_for(user)

    assert user.is_staff_user()
    assert IsDjangoSalesperson().has_permission(request, None)
    assert IsDrupalSalesperson().has_permission(request, None)


@pytest.mark.django_db
def test_user_without_sales_access_fails_sales_permissions():
    """
    - a user without any sales group is denied by IsDjangoSalesperson
    - a user without any sales group is denied by IsDrupalSalesperson
    """
    user = UserFactory(uuid=uuid.UUID(USER_UUID))
    request = _request_for(user)

    assert not user.is_staff_user()
    assert not IsDjangoSalesperson().has_permission(request, None)
    assert not IsDrupalSalesperson().has_permission(request, None)


@pytest.mark.django_db
def test_staff_survives_sync_groups_from_ad_with_mapping():
    """
    - an ADGroupMapping maps django_salesperson to an AD group the user is not in
    - sync_groups_from_ad removes django_salesperson from the user
    - sync_groups_from_ad keeps the unmapped staff group
    - the user still passes both sales permissions after the sync
    """
    ad_group = ADGroup.objects.create(
        name="example-prod-sales-group", display_name="example-prod-sales-group"
    )
    ADGroupMapping.objects.create(
        group=_group(Roles.DJANGO_SALESPERSON), ad_group=ad_group
    )
    user = grant_sales_access(USER_UUID)
    _group(Roles.DJANGO_SALESPERSON).user_set.add(user)
    assert user.is_django_salesperson()

    user.sync_groups_from_ad()

    user.refresh_from_db()
    assert not user.is_django_salesperson()
    assert user.is_staff_user()
    request = _request_for(user)
    assert IsDjangoSalesperson().has_permission(request, None)
    assert IsDrupalSalesperson().has_permission(request, None)


@pytest.mark.django_db
def test_command_grants_access_for_multiple_uuids():
    """
    - every uuid given to the command gets a user
    - every such user is in the staff group
    """
    call_command("grant_sales_access", USER_UUID, OTHER_USER_UUID, stdout=StringIO())

    for value in (USER_UUID, OTHER_USER_UUID):
        user = User.objects.get(uuid=value)
        assert user.is_staff_user()


@pytest.mark.django_db
def test_command_output_contains_uuids():
    """
    - stdout contains each granted uuid
    - one line is printed per user
    """
    out = StringIO()

    call_command("grant_sales_access", USER_UUID, OTHER_USER_UUID, stdout=out)

    output = out.getvalue()
    lines = [line for line in output.splitlines() if line.strip()]
    assert USER_UUID in output
    assert OTHER_USER_UUID in output
    assert len(lines) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("invalid", INVALID_UUIDS)
def test_command_with_invalid_uuid_makes_no_changes(invalid):
    """
    - one invalid uuid among valid ones raises CommandError
    - no user is created for the valid uuids
    - an existing user given as a valid uuid is not added to the staff group
    """
    existing = UserFactory(uuid=uuid.UUID(OTHER_USER_UUID))
    user_count = User.objects.count()
    staff_count = _group(Roles.STAFF).user_set.count()

    with pytest.raises(CommandError):
        call_command(
            "grant_sales_access",
            USER_UUID,
            OTHER_USER_UUID,
            invalid,
            stdout=StringIO(),
        )

    assert User.objects.count() == user_count
    assert not User.objects.filter(uuid=USER_UUID).exists()
    assert _group(Roles.STAFF).user_set.count() == staff_count
    existing.refresh_from_db()
    assert not existing.is_staff_user()


@pytest.mark.django_db
def test_command_without_arguments_raises_command_error():
    """
    - calling the command without any uuid raises CommandError
    - no user is created
    """
    user_count = User.objects.count()

    with pytest.raises(CommandError):
        call_command("grant_sales_access", stdout=StringIO())

    assert User.objects.count() == user_count
