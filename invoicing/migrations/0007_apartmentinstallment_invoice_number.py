# Generated by Django 3.2.12 on 2022-03-31 08:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "invoicing",
            "0006_change_right_of_residence_fee_to_right_of_occupancy_payment",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="apartmentinstallment",
            name="invoice_number",
            field=models.CharField(
                default="", max_length=9, verbose_name="invoice number"
            ),
            preserve_default=False,
        ),
    ]
