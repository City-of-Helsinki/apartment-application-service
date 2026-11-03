import json

from django.core.management.base import BaseCommand, CommandError

from users.masking import mask_uuid
from users.services.drupal_credentials import (
    credentials_to_json,
    find_profile_for_drupal_user,
    ProfileNotFoundError,
    ProfileUserMissingError,
    sync_drupal_user_credentials,
)


class Command(BaseCommand):
    help = (
        "Reset a Django profile password and output masked credentials for "
        "Drupal field_backend_profile and field_backend_password."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--drupal-uuid",
            required=True,
            help="Drupal user entity UUID.",
        )
        parser.add_argument(
            "--email",
            default="",
            help="Drupal user email (fallback profile lookup).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Resolve the profile without resetting the password.",
        )

    def handle(self, *args, **options):
        try:
            if options["dry_run"]:
                profile = find_profile_for_drupal_user(
                    options["drupal_uuid"], options["email"]
                )
                if profile.user is None:
                    raise ProfileUserMissingError(
                        f"Profile {profile.pk} has no linked Django user"
                    )
                payload = {
                    "profile_pk": str(profile.pk),
                    "profile_id": mask_uuid(profile.pk),
                    "dry_run": True,
                }
                self.stdout.write(json.dumps(payload))
                return

            credentials = sync_drupal_user_credentials(
                options["drupal_uuid"],
                options["email"],
                dry_run=False,
            )
        except (ProfileNotFoundError, ProfileUserMissingError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(credentials_to_json(credentials))
