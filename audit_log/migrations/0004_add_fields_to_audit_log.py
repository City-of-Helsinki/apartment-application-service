# Generated by Django 3.2.12 on 2022-09-13 12:13

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit_log", "0003_noncontrib_jsonfield"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="created at",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="auditlog",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="sent at"),
        ),
    ]
