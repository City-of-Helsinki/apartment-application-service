import enumfields.fields
from django.db import migrations

import apartment.enums


class Migration(migrations.Migration):

    dependencies = [
        ("apartment", "0008_add_uuid_to_apartment_project_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="ownership_type",
            field=enumfields.fields.EnumField(
                default="haso", enum=apartment.enums.OwnershipType, max_length=10
            ),
        ),
    ]
