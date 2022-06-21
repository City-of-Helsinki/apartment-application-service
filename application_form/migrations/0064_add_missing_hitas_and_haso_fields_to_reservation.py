# Generated by Django 3.2.13 on 2022-06-20 10:04

from django.db import migrations
import pgcrypto.fields


def populate_reservation_hitas_and_haso_fields(apps, schema_editor):
    ApartmentReservation = apps.get_model("application_form", "ApartmentReservation")

    for reservation in ApartmentReservation.objects.all():
        if reservation.application_apartment:
            source = reservation.application_apartment.application
        else:
            source = reservation.customer
        update_data = {
            field: getattr(source, field)
            for field in (
                "has_children",
                "has_hitas_ownership",
                "is_right_of_occupancy_housing_changer",
            )
        }
        update_data["is_age_over_55"] = reservation.customer.is_age_over_55
        ApartmentReservation.objects.filter(pk=reservation.pk).update(**update_data)


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0063_add_right_of_residence_to_reservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="apartmentreservation",
            name="has_children",
            field=pgcrypto.fields.BooleanPGPPublicKeyField(
                blank=True, null=True, verbose_name="has children"
            ),
        ),
        migrations.AddField(
            model_name="apartmentreservation",
            name="has_hitas_ownership",
            field=pgcrypto.fields.BooleanPGPPublicKeyField(
                blank=True, null=True, verbose_name="has hitas ownership"
            ),
        ),
        migrations.AddField(
            model_name="apartmentreservation",
            name="is_age_over_55",
            field=pgcrypto.fields.BooleanPGPPublicKeyField(
                blank=True, null=True, verbose_name="is age over 55"
            ),
        ),
        migrations.AddField(
            model_name="apartmentreservation",
            name="is_right_of_occupancy_housing_changer",
            field=pgcrypto.fields.BooleanPGPPublicKeyField(
                blank=True,
                null=True,
                verbose_name="is right-of-occupancy housing changer",
            ),
        ),
        migrations.RunPython(
            populate_reservation_hitas_and_haso_fields, migrations.RunPython.noop
        ),
    ]
