# Generated by Django 2.2.24 on 2021-06-14 12:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_alter_field_street_address"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="profile",
            name="right_of_residence",
        ),
    ]
