# Generated by Django 2.2.16 on 2020-11-03 06:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0005_occupancy_id_to_int"),
    ]

    operations = [
        migrations.AddField(
            model_name="hitasapplication",
            name="order",
            field=models.PositiveIntegerField(default=1, verbose_name="order"),
            preserve_default=False,
        ),
    ]