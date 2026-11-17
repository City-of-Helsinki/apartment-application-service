from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from users.models import Profile
from users.services.drupal_credentials import build_restore_credentials_sql

CONFIRM_FLAG = "--i-know-this-is-a-restored-dump"


class Command(BaseCommand):
    help = (
        "Print MariaDB SQL that re-links a restored sanitized Drupal dump to this "
        "backend by recomputing masked field_backend_profile and "
        "field_backend_password values with this environment's HASHIDS_SALT. "
        "Only for environments restored from sanitized dumps: applying the SQL "
        "sets every Drupal user's backend password to SANITIZED_DUMP_PASSWORD, "
        "which must match the value used when the dump was made."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            CONFIRM_FLAG,
            action="store_true",
            dest="confirmed",
            help="Required. Confirms this environment was restored from dumps.",
        )

    def handle(self, *args, **options):
        if not options["confirmed"]:
            raise CommandError(
                f"Refusing to run without {CONFIRM_FLAG}. Only use this after "
                "restoring sanitized Django and Drupal dumps."
            )

        profiles = Profile.objects.filter(user__isnull=False).only("id", "user")
        try:
            for statement in build_restore_credentials_sql(profiles.iterator()):
                self.stdout.write(statement)
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc
