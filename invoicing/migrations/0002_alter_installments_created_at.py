# Generated by Django 3.2.6 on 2022-01-24 07:48

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apartmentinstallment",
            name="created_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
                verbose_name="created at",
            ),
        ),
        migrations.AlterField(
            model_name="projectinstallmenttemplate",
            name="created_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
                verbose_name="created at",
            ),
        ),
    ]
