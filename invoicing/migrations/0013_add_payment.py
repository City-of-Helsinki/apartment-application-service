# Generated by Django 3.2.15 on 2023-01-03 11:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0012_add_updated_at_to_installments"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=16, verbose_name="amount"
                    ),
                ),
                ("payment_date", models.DateField(verbose_name="payment date")),
                (
                    "apartment_installment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="invoicing.apartmentinstallment",
                        verbose_name="apartment installment",
                    ),
                ),
            ],
            options={
                "verbose_name": "payment",
                "verbose_name_plural": "payments",
                "ordering": ("id",),
            },
        ),
    ]
