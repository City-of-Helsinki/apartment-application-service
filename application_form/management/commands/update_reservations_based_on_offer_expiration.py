from django.core.management.base import BaseCommand

from application_form.services.offer import (
    update_reservations_based_on_offer_expiration,
)


class Command(BaseCommand):
    help = (
        "Update apartment reservations' states based on their offers' expiration state."
    )

    def handle(self, *args, **options):
        self.stdout.write("Updating reservations' states based on offer expiration...")
        (
            num_of_expired,
            num_of_unexpired,
        ) = update_reservations_based_on_offer_expiration()
        self.stdout.write(
            f'Done! Set {num_of_expired} reservation(s) "expired" and '
            f'{num_of_unexpired} reservation(s) back to "offered".'
        )
