# Generated by Django 3.2.15 on 2023-10-18 19:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("application_form", "0069_add_right_of_residence_is_old_batch"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lotteryevent",
            name="apartment_uuid",
            field=models.UUIDField(db_index=True, verbose_name="apartment uuid"),
        ),
    ]
