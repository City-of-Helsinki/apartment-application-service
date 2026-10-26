"""
Reset and load the Django e2e fixtures (e2e/fixtures/django/*.json).

Deletes every reservation and lottery event on the baseline apartments
(e2e/fixtures/drupal/baseline.json), including rows tests created there, and
then loads the fixture files with loaddata. Fixture rows are upserted by pk,
so running this again restores them to their committed state.

Run on django-app startup and by run-e2e.sh before every test run.

Usage: python load_django_fixtures.py

The Django project must be importable (e.g. PYTHONPATH=/app in the
container) since this script lives outside the project directory.
"""

import json
import os
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
BASELINE_FILE = FIXTURES_DIR / "drupal" / "baseline.json"
DJANGO_FIXTURES = sorted((FIXTURES_DIR / "django").glob("*.json"))


def baseline_apartment_uuids():
    """
    Return the apartment uuids of the Drupal baseline.

            Returns:
                    uuids (list[str]): Apartment uuids of every baseline project
    """
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return [
        apartment["uuid"]
        for project in data["projects"]
        for apartment in project["apartments"]
    ]


def reset(apartment_uuids):
    """
    Delete the reservations and lottery events on the given apartments.

    Rows that protect a reservation from deletion are deleted first.

            Parameters:
                    apartment_uuids (list[str]): Apartments to reset
    """
    from application_form.models import ApartmentReservation, LotteryEvent, Offer
    from cost_index.models import ApartmentRevaluation
    from invoicing.models import (
        ApartmentInstallment,
        DrupalPaymentSyncOutboxEvent,
        Payment,
    )

    ids = list(
        ApartmentReservation.objects.filter(
            apartment_uuid__in=apartment_uuids
        ).values_list("pk", flat=True)
    )
    installment_filter = {"apartment_installment__apartment_reservation_id__in": ids}
    Payment.objects.filter(**installment_filter).delete()
    DrupalPaymentSyncOutboxEvent.objects.filter(**installment_filter).delete()
    ApartmentInstallment.objects.filter(apartment_reservation_id__in=ids).delete()
    ApartmentRevaluation.objects.filter(apartment_reservation_id__in=ids).delete()
    Offer.objects.filter(apartment_reservation_id__in=ids).delete()
    ApartmentReservation.objects.filter(pk__in=ids).delete()
    LotteryEvent.objects.filter(apartment_uuid__in=apartment_uuids).delete()


def main():
    """
    Reset the baseline apartments and load the fixtures in one transaction.
    """
    from django.core.management import call_command
    from django.db import transaction

    with transaction.atomic():
        reset(baseline_apartment_uuids())
        call_command("loaddata", *map(str, DJANGO_FIXTURES))


if __name__ == "__main__":
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "apartment_application_service.settings"
    )
    import django

    django.setup()
    sys.exit(main())
