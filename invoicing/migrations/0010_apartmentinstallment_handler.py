# Generated by Django 3.2.12 on 2022-07-13 11:40

import pgcrypto.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "invoicing",
            "0009_change_debt_free_sales_price_flexible_to_sales_price_flexible",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="apartmentinstallment",
            name="handler",
            field=pgcrypto.fields.CharPGPPublicKeyField(
                blank=True, max_length=200, verbose_name="handler"
            ),
        ),
    ]
