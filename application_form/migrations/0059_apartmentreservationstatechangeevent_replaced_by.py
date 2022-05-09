# Generated by Django 3.2.12 on 2022-05-02 01:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "application_form",
            "0058_apartmentreservation_apt_uuid_list_pos_unq_def_const",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="apartmentreservationstatechangeevent",
            name="replaced_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replaced_reservation_state_change_events",
                to="application_form.apartmentreservation",
                verbose_name="replaced by",
            ),
        ),
    ]