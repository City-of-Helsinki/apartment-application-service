# Generated by Django 2.2.24 on 2021-06-23 08:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apartment", "0005_alter_field_schema_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apartment",
            name="apartment_number",
            field=models.CharField(max_length=10, verbose_name="apartment number"),
        ),
    ]