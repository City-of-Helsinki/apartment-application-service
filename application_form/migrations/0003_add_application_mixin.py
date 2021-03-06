# Generated by Django 2.2.16 on 2020-10-16 12:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0002_rename_application_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="hasoapplication",
            name="applicant_has_accepted_offer",
            field=models.BooleanField(
                default=False, verbose_name="applicant has accepted offer"
            ),
        ),
        migrations.AddField(
            model_name="hasoapplication",
            name="is_approved",
            field=models.BooleanField(default=False, verbose_name="is accepted"),
        ),
        migrations.AddField(
            model_name="hasoapplication",
            name="is_rejected",
            field=models.BooleanField(default=False, verbose_name="is rejected"),
        ),
        migrations.AddField(
            model_name="hasoapplication",
            name="rejection_description",
            field=models.TextField(default="", verbose_name="rejection description"),
        ),
        migrations.AddField(
            model_name="hitasapplication",
            name="applicant_has_accepted_offer",
            field=models.BooleanField(
                default=False, verbose_name="applicant has accepted offer"
            ),
        ),
        migrations.AddField(
            model_name="hitasapplication",
            name="is_approved",
            field=models.BooleanField(default=False, verbose_name="is accepted"),
        ),
        migrations.AddField(
            model_name="hitasapplication",
            name="is_rejected",
            field=models.BooleanField(default=False, verbose_name="is rejected"),
        ),
        migrations.AddField(
            model_name="hitasapplication",
            name="rejection_description",
            field=models.TextField(default="", verbose_name="rejection description"),
        ),
    ]
