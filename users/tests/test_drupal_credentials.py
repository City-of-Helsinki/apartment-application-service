import json
from io import StringIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError

from users.masking import mask_string, mask_uuid, unmask_string
from users.services.drupal_credentials import (
    build_masked_credentials,
    build_restore_credentials_sql,
    credentials_to_json,
    find_profile_for_drupal_user,
    ProfileNotFoundError,
    ProfileUserMissingError,
    sync_drupal_user_credentials,
)
from users.tests.conftest import PROFILE_TEST_DATA, TEST_USER_PASSWORD
from users.tests.utils import _create_profile


@pytest.mark.django_db
def test_find_profile_by_drupal_uuid(profile):
    """
    - Profile is found when Drupal UUID matches profile primary key.
    """
    found = find_profile_for_drupal_user(str(profile.pk), email="other@example.com")
    assert found.pk == profile.pk


@pytest.mark.django_db
def test_find_profile_by_email_when_uuid_missing(other_profile):
    """
    - Profile is found by email when UUID does not match any profile.
    """
    found = find_profile_for_drupal_user(
        "00000000-0000-0000-0000-000000000001",
        email=other_profile.email,
    )
    assert found.pk == other_profile.pk


@pytest.mark.django_db
def test_find_profile_raises_when_not_found():
    """
    - ProfileNotFoundError is raised when neither UUID nor email match.
    """
    with pytest.raises(ProfileNotFoundError):
        find_profile_for_drupal_user(
            "00000000-0000-0000-0000-000000000001",
            email="missing@example.com",
        )


@pytest.mark.django_db
def test_build_masked_credentials_resets_password(profile):
    """
    - A new random password is stored on the profile user.
    - Masked credentials are returned for Drupal.
    """
    old_password_hash = profile.user.password

    credentials = build_masked_credentials(profile)

    profile.user.refresh_from_db()
    assert profile.user.password != old_password_hash
    assert profile.user.check_password(unmask_string(credentials["password"]))
    assert credentials["profile_id"]
    assert credentials["password"]
    assert credentials["profile_pk"] == str(profile.pk)


@pytest.mark.django_db
def test_build_masked_credentials_dry_run_does_not_change_password(profile):
    """
    - dry_run leaves the stored password hash unchanged.
    """
    old_password_hash = profile.user.password

    build_masked_credentials(profile, dry_run=True)

    profile.user.refresh_from_db()
    assert profile.user.password == old_password_hash


@pytest.mark.django_db
def test_build_masked_credentials_raises_without_user():
    """
    - ProfileUserMissingError is raised when profile.user is null.
    """
    profile = _create_profile(PROFILE_TEST_DATA, TEST_USER_PASSWORD)
    profile.user = None
    profile.save(update_fields=["user"])

    with pytest.raises(ProfileUserMissingError):
        build_masked_credentials(profile)


@pytest.mark.django_db
def test_sync_drupal_user_credentials_returns_json_serializable_data(profile):
    """
    - End-to-end sync returns masked values for Drupal fields.
    """
    credentials = sync_drupal_user_credentials(str(profile.pk), email=profile.email)
    payload = json.loads(credentials_to_json(credentials))

    assert UUID(payload["profile_pk"]) == profile.pk
    assert payload["profile_id"]
    assert payload["password"]


@pytest.mark.django_db
def test_build_restore_credentials_sql_maps_profiles(profile, other_profile):
    """
    - Each profile with a user is mapped from its UUID to its masked profile id.
    - Profiles without a user are skipped.
    - The backend password is set to the masked SANITIZED_DUMP_PASSWORD.
    - Statements are wrapped in one transaction.
    - Map columns are ASCII so the join does not hit a MariaDB collation clash.
    """
    other_profile.user = None
    other_profile.save(update_fields=["user"])

    statements = list(build_restore_credentials_sql([profile, other_profile]))
    sql = "\n".join(statements)

    assert statements[0] == "START TRANSACTION;"
    assert statements[-1] == "COMMIT;"
    assert statements[1].count("CHARACTER SET ascii") == 2
    assert f"('{profile.pk}', '{mask_uuid(profile.pk)}')" in sql
    assert str(other_profile.pk) not in sql
    password = django_settings.SANITIZED_DUMP_PASSWORD
    assert f"'{mask_string(password)}'" in sql
    assert unmask_string(mask_string(password)) == password


def test_build_restore_credentials_sql_requires_dump_password(settings):
    """
    - Without SANITIZED_DUMP_PASSWORD the generator raises before yielding SQL,
      so no partial fix.sql is written.
    """
    settings.SANITIZED_DUMP_PASSWORD = ""
    statements = build_restore_credentials_sql([])

    with pytest.raises(ImproperlyConfigured):
        next(statements)


def test_build_restore_credentials_sql_batches_inserts():
    """
    - Map rows are split into INSERT statements of at most batch_size rows.
    """
    profiles = [SimpleNamespace(pk=UUID(int=i + 1), user_id=i + 1) for i in range(5)]

    inserts = [
        statement
        for statement in build_restore_credentials_sql(profiles, batch_size=2)
        if statement.startswith("INSERT")
    ]

    assert len(inserts) == 3
    assert inserts[-1].count("('") == 1


def test_build_restore_credentials_sql_without_profiles_has_no_insert():
    """
    - No profiles produces no INSERT, but the UPDATEs still run.
    """
    statements = list(build_restore_credentials_sql([]))

    assert not any(statement.startswith("INSERT") for statement in statements)
    assert any(
        statement.startswith("UPDATE user__field_backend_password")
        for statement in statements
    )


@pytest.mark.django_db
def test_drupal_restore_credentials_sql_command_requires_confirmation():
    """
    - The command refuses to run without the confirmation flag.
    """
    with pytest.raises(CommandError):
        call_command("drupal_restore_credentials_sql")


@pytest.mark.django_db
def test_drupal_restore_credentials_sql_command_prints_sql(profile):
    """
    - With the confirmation flag, SQL for existing profiles is printed.
    """
    out = StringIO()

    call_command(
        "drupal_restore_credentials_sql",
        "--i-know-this-is-a-restored-dump",
        stdout=out,
    )

    assert f"('{profile.pk}', '{mask_uuid(profile.pk)}')" in out.getvalue()


@pytest.mark.django_db
def test_drupal_restore_credentials_sql_command_requires_dump_password(settings):
    """
    - Without SANITIZED_DUMP_PASSWORD the command fails with a clear error
      and prints no SQL.
    """
    settings.SANITIZED_DUMP_PASSWORD = ""
    out = StringIO()

    with pytest.raises(CommandError, match="SANITIZED_DUMP_PASSWORD"):
        call_command(
            "drupal_restore_credentials_sql",
            "--i-know-this-is-a-restored-dump",
            stdout=out,
        )
    assert out.getvalue() == ""
