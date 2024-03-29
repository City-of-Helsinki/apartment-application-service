# Generated by Django 3.2.11 on 2022-02-13 21:11

from django.db import migrations


def populate_apartment_reservation_customer(apps, schema_editor):
    ApplicationApartment = apps.get_model("application_form", "ApplicationApartment")

    for application_apartment in ApplicationApartment.objects.all():
        application_apartment.apartment_reservation.customer = (
            application_apartment.application.customer
        )
        application_apartment.apartment_reservation.save(update_fields=("customer",))


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0049_apartmentreservation_customer"),
    ]

    operations = [
        migrations.RunPython(
            populate_apartment_reservation_customer, migrations.RunPython.noop
        ),
    ]
