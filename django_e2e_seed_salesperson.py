"""
Seed a Django salesperson user for the E2E stack.
Ensures a user with the given UUID exists and belongs to the
django_salesperson group, so Bearer tokens from the mock OIDC provider
carrying that UUID as `sub` pass the sales API permission checks.

Usage: python django_e2e_seed_salesperson.py <user-uuid>

The Django project must be importable (e.g. PYTHONPATH=/app in the
container) since this script lives outside the project directory.
"""

import os
import sys
import uuid

USAGE = "Usage: python django_e2e_seed_salesperson.py <user-uuid>"


def ensure_salesperson(user_uuid):
    """
    Get or create the user with the given UUID and add it to the
    django_salesperson group. Idempotent.

            Parameters:
                    user_uuid (str): UUID of the user (the OIDC token `sub`)

            Returns:
                    user (User): The existing or newly created user

            Raises:
                    ValueError: If user_uuid is not a valid UUID
    """
    # Validated before any DB access so invalid input never writes anything.
    parsed_uuid = uuid.UUID(str(user_uuid))

    # Imported lazily so importing this module needs no configured Django.
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.db import transaction
    from helusers.utils import uuid_to_username

    from users.enums import Roles

    user_model = get_user_model()
    with transaction.atomic():
        user, _ = user_model.objects.get_or_create(
            uuid=parsed_uuid,
            defaults={"username": uuid_to_username(parsed_uuid)},
        )
        group = Group.objects.get(name__iexact=Roles.DJANGO_SALESPERSON.name)
        user.groups.add(group)
    return user


def main(argv=None):
    """
    Seed the salesperson user given on the command line.

            Parameters:
                    argv (list[str] | None): A single user UUID; defaults to
                    sys.argv[1:]

            Returns:
                    exit_code (int): 0 on success, 2 on invalid arguments
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        user = ensure_salesperson(args[0])
    except ValueError:
        print(f"[e2e] Invalid user UUID: {args[0]!r}", file=sys.stderr)
        return 2

    print(f"[e2e] Salesperson {user.uuid} seeded", file=sys.stderr)
    return 0


if __name__ == "__main__":
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "apartment_application_service.settings"
    )
    import django

    django.setup()
    sys.exit(main())
