from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0002_add_customer_primary_and_secondary_profile"),
        ("application_form", "0043_remove_apartmentreservation_apartment"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="customer",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="customer.customer",
            ),
        ),
    ]
