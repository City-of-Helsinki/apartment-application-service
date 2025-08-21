import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0008_customercomment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="customercomment",
            name="author",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_comments",
                to="users.profile",
                verbose_name="author",
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="customercomment",
            name="author_user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_comments",
                to=settings.AUTH_USER_MODEL,
                verbose_name="author user",
                null=True,
                blank=True,
            ),
        ),
    ]
