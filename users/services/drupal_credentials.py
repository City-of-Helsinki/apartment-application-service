"""Sync masked API credentials between Django profiles and Drupal users."""

import json
import logging
from uuid import UUID

from django.contrib.auth import get_user_model

from users.masking import mask_string, mask_uuid
from users.models import Profile

_logger = logging.getLogger(__name__)


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


def credentials_to_json(credentials: dict) -> str:
    """Serialize credentials for machine-readable command output."""
    return json.dumps(
        {
            "profile_id": credentials["profile_id"],
            "password": credentials["password"],
            "profile_pk": credentials["profile_pk"],
        }
    )
