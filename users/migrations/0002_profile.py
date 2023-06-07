# Generated by Django 2.2.21 on 2021-05-11 09:47

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True,
                        serialize=False,
                        verbose_name="user identifier",
                    ),
                ),
                (
                    "phone_number",
                    models.CharField(max_length=15, verbose_name="phone number"),
                ),
                ("address", models.CharField(max_length=200, verbose_name="address")),
                ("date_of_birth", models.DateField(verbose_name="date of birth")),
                ("city", models.CharField(max_length=50, verbose_name="city")),
                (
                    "postal_code",
                    models.CharField(max_length=5, verbose_name="postal code"),
                ),
                (
                    "right_of_residence",
                    models.CharField(
                        max_length=10, verbose_name="right of residence number"
                    ),
                ),
                (
                    "contact_language",
                    models.CharField(
                        choices=[
                            ("fi", "Finnish"),
                            ("sv", "Swedish"),
                            ("en", "English"),
                        ],
                        max_length=2,
                        verbose_name="contact language",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "profile",
                "verbose_name_plural": "profiles",
            },
        ),
    ]
