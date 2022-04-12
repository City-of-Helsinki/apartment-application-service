# Generated by Django 3.2.12 on 2022-03-25 13:28

import application_form.enums
from django.db import migrations
import enumfields.fields


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0051_alter_apartmentreservation_customer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apartmentreservation",
            name="state",
            field=enumfields.fields.EnumField(
                default="submitted",
                enum=application_form.enums.ApartmentReservationState,
                max_length=32,
                verbose_name="apartment reservation state",
            ),
        ),
    ]