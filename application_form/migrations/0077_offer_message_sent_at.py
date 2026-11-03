from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0075_offer_reminder_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="offer",
            name="message_sent_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="message sent at"
            ),
        ),
    ]
