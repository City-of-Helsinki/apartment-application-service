import uuid
from django.db import migrations, models


def forwards_func(apps, schema_editor):
    application_apartment = apps.get_model("application_form", "ApplicationApartment")
    for item in application_apartment.objects.all():
        item.aparment_uuid = item.apartment.uuid
        item.save(update_fields=["apartment_uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("apartment", "0010_bigauto_pk_field"),
        ("application_form", "0037_alter_apartmentreservation_apartment"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationapartment",
            name="apartment_uuid",
            field=models.UUIDField(
                default=uuid.UUID(int=0),
                verbose_name="apartment uuid",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(forwards_func, reverse_code=migrations.RunPython.noop),
    ]
