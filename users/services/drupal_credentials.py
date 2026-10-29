"""Sync masked API credentials between Django profiles and Drupal users."""

import json
import logging
from typing import Iterable, Iterator
from uuid import UUID

from django.contrib.auth import get_user_model

from sanitizers.person import dump_password
from users.masking import mask_string, mask_uuid
from users.models import Profile

_logger = logging.getLogger(__name__)

RESTORE_MAP_TABLE = "asu_restore_backend_profile_map"
RESTORE_INSERT_BATCH_SIZE = 1000


class ProfileNotFoundError(Exception):
    """Raised when no Django profile matches the Drupal user."""


class ProfileUserMissingError(Exception):
    """Raised when the profile has no linked Django auth user."""


def find_profile_for_drupal_user(drupal_uuid: str, email: str = "") -> Profile:
    """
    Find a Django profile for a Drupal user.

    Lookup order:
    1. Profile primary key equal to the Drupal user UUID.
    2. Profile email equal to the Drupal user email (newest profile wins).

    Parameters:
        drupal_uuid: Drupal user entity UUID.
        email: Drupal user email address.

    Returns:
        Matching Profile instance.

    Raises:
        ProfileNotFoundError: No profile could be resolved.
    """
    try:
        uuid = UUID(drupal_uuid)
    except ValueError as exc:
        raise ProfileNotFoundError(f"Invalid Drupal UUID: {drupal_uuid}") from exc

    try:
        return Profile.objects.select_related("user").get(pk=uuid)
    except Profile.DoesNotExist:
        pass

    if not email:
        raise ProfileNotFoundError(
            f"No profile with id {drupal_uuid} and no email to fall back on"
        )

    profiles = Profile.objects.filter(email=email).select_related("user")
    count = profiles.count()
    if count == 0:
        raise ProfileNotFoundError(
            f"No profile for Drupal UUID {drupal_uuid} or email {email}"
        )

    if count > 1:
        _logger.warning(
            "Multiple profiles (%s) for email %s; using newest",
            count,
            email,
        )

    return profiles.order_by("-created_at").first()


def build_masked_credentials(profile: Profile, *, dry_run: bool = False) -> dict:
    """
    Reset the profile user's password and return masked API credentials.

    Parameters:
        profile: Django profile linked to the Drupal user.
        dry_run: When True, do not persist a new password.

    Returns:
        Dict with masked profile_id and password keys.

    Raises:
        ProfileUserMissingError: Profile has no auth user to authenticate.
    """
    user = profile.user
    if user is None:
        raise ProfileUserMissingError(f"Profile {profile.pk} has no linked Django user")

    User = get_user_model()
    password = User.objects.make_random_password(length=32)

    if not dry_run:
        user.set_password(password)
        user.save(update_fields=["password"])

    return {
        "profile_id": mask_uuid(profile.pk),
        "password": mask_string(password),
        "profile_pk": str(profile.pk),
    }


def sync_drupal_user_credentials(
    drupal_uuid: str, email: str = "", *, dry_run: bool = False
) -> dict:
    """
    Resolve a profile and return masked credentials for Drupal storage.

    Parameters:
        drupal_uuid: Drupal user entity UUID.
        email: Drupal user email for fallback lookup.
        dry_run: When True, skip password reset.

    Returns:
        Credential dict suitable for Drupal field_backend_* fields.
    """
    profile = find_profile_for_drupal_user(drupal_uuid, email)
    return build_masked_credentials(profile, dry_run=dry_run)


def build_restore_credentials_sql(
    profiles: Iterable[Profile], batch_size: int = RESTORE_INSERT_BATCH_SIZE
) -> Iterator[str]:
    """
    Yield MariaDB statements that re-link a restored Drupal dump to this backend.

    Drupal stores field_backend_profile / field_backend_password masked with
    the source environment's HASHIDS_SALT. After restoring sanitized dumps into
    another environment, recompute both with this environment's salt. Django
    passwords in a sanitized dump are all SANITIZED_DUMP_PASSWORD, so no reset
    is needed; it must have the same value here as when the dump was made.
    Profiles are matched to Drupal users by Profile.id == users.uuid.

    Parameters:
        profiles: Profiles to link; profiles without a user are skipped.
        batch_size: Rows per INSERT statement.

    Yields:
        SQL statements, one per item, wrapped in a single transaction.

    Raises:
        ImproperlyConfigured: When SANITIZED_DUMP_PASSWORD is not set, before
            any statement is yielded.
    """
    masked_password = mask_string(dump_password())
    yield "START TRANSACTION;"
    # ASCII columns: a server-default collation would clash with Drupal's
    # utf8mb4 collation on the users.uuid join (MariaDB error 1267).
    yield (
        f"CREATE TEMPORARY TABLE {RESTORE_MAP_TABLE} "
        "(uuid VARCHAR(128) CHARACTER SET ascii PRIMARY KEY, "
        "masked_profile_id VARCHAR(255) CHARACTER SET ascii NOT NULL);"
    )

    # Values are UUIDs and Hashids output (alphanumeric), so no quoting issues.
    rows = (
        f"('{profile.pk}', '{mask_uuid(profile.pk)}')"
        for profile in profiles
        if profile.user_id is not None
    )
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) == batch_size:
            yield f"INSERT INTO {RESTORE_MAP_TABLE} VALUES {', '.join(batch)};"
            batch = []
    if batch:
        yield f"INSERT INTO {RESTORE_MAP_TABLE} VALUES {', '.join(batch)};"

    yield (
        "UPDATE user__field_backend_profile f "
        "JOIN users u ON u.uid = f.entity_id "
        f"JOIN {RESTORE_MAP_TABLE} m ON m.uuid = u.uuid "
        "SET f.field_backend_profile_value = m.masked_profile_id;"
    )
    yield (
        "UPDATE user__field_backend_password "
        f"SET field_backend_password_value = '{masked_password}' "
        "WHERE field_backend_password_value <> '';"
    )
    yield f"DROP TEMPORARY TABLE {RESTORE_MAP_TABLE};"
    yield "COMMIT;"


def credentials_to_json(credentials: dict) -> str:
    """Serialize credentials for machine-readable command output."""
    return json.dumps(
        {
            "profile_id": credentials["profile_id"],
            "password": credentials["password"],
            "profile_pk": credentials["profile_pk"],
        }
    )
