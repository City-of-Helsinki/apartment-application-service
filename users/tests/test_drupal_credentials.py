import json
from uuid import UUID

import pytest

from users.masking import unmask_string
from users.services.drupal_credentials import (
    ProfileNotFoundError,
    ProfileUserMissingError,
    build_masked_credentials,
    credentials_to_json,
    find_profile_for_drupal_user,
    sync_drupal_user_credentials,
)
from users.tests.conftest import PROFILE_TEST_DATA, TEST_USER_PASSWORD
from users.tests.utils import _create_profile


@pytest.mark.django_db
def test_find_profile_by_drupal_uuid(profile):
    """
    - Profile is found when Drupal UUID matches profile primary key.
    """
    found = find_profile_for_drupal_user(
        str(profile.pk), email="other@example.com"
    )
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
    credentials = sync_drupal_user_credentials(
        str(profile.pk), email=profile.email
    )
    payload = json.loads(credentials_to_json(credentials))

    assert UUID(payload["profile_pk"]) == profile.pk
    assert payload["profile_id"]
    assert payload["password"]
