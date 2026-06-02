from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "application_form",
            "0074_apartmentreservation_queue_position_before_cancelation",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="offer",
            name="reminder_sent_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="reminder sent at"
            ),
        ),
    ]
