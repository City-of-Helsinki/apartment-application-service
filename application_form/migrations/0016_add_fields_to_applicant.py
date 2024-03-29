# Generated by Django 2.2.21 on 2021-06-03 13:10

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0015_add_application_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="application",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="applicants",
                to="application_form.Application",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applicant",
            name="city",
            field=models.CharField(default="s", max_length=50, verbose_name="city"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applicant",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applicant",
            name="phone_number",
            field=models.CharField(
                default="s", max_length=40, verbose_name="phone number"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applicant",
            name="postal_code",
            field=models.CharField(
                default="s", max_length=10, verbose_name="postal code"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applicant",
            name="street_address",
            field=models.CharField(
                default="s", max_length=200, verbose_name="street address"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applicant",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
