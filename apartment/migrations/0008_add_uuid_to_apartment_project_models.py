import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apartment", "0007_apartment_room_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="apartment",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="project",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
