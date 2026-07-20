from django.db import migrations
from django.utils import timezone


def backfill_message_sent_at(apps, schema_editor):
    """
    Mark existing offers as already messaged so deploy does not re-email them.
    """
    Offer = apps.get_model("application_form", "Offer")
    Offer.objects.filter(message_sent_at__isnull=True).update(
        message_sent_at=timezone.now()
    )


def noop_reverse(apps, schema_editor):
    """
    Irreversible data backfill; reverse is a no-op.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0077_offer_message_sent_at"),
    ]

    operations = [
        migrations.RunPython(backfill_message_sent_at, noop_reverse),
    ]
