from django.db.models import DateField, DecimalField, Model


class CostIndex(Model):
    valid_from = DateField(unique=True)
    value = DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["-valid_from"]
