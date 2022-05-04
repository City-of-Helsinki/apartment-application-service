# Generated by Django 3.2.12 on 2022-04-22 08:49

import django.db.models.constraints
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0057_apartmentreservation_list_position"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apartmentreservation",
            name="list_position",
            field=models.IntegerField(verbose_name="position in list"),
        ),
        migrations.AddConstraint(
            model_name="apartmentreservation",
            constraint=models.UniqueConstraint(
                deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                fields=("apartment_uuid", "list_position"),
                name="apt_uuid_list_pos_unq_def_const",
            ),
        ),
    ]