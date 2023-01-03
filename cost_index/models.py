from django.db.models import DateField, DecimalField, Model, OneToOneField, PROTECT

from apartment_application_service.models import TimestampedModel


class CostIndex(Model):
    valid_from = DateField(unique=True)
    value = DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["-valid_from"]


class ApartmentRevaluation(TimestampedModel):
    """
    A model to keep all information related to termination of a HASO
    reservation and recalculation of right of occupancy value of the apartment.

    Cost index fields are saved as values instead of references, as this makes
    it possible to discover entries that require manual intervention in case
    a cost index is changed retroactively.
    """

    apartment_reservation = OneToOneField(
        "application_form.ApartmentReservation",
        on_delete=PROTECT,
        related_name="revaluation",
    )

    start_date = DateField()
    start_cost_index_value = DecimalField(max_digits=16, decimal_places=2)
    start_right_of_occupancy_payment = DecimalField(max_digits=16, decimal_places=2)

    alteration_work = DecimalField(max_digits=16, decimal_places=2)

    end_date = DateField()
    end_cost_index_value = DecimalField(max_digits=16, decimal_places=2)
    end_right_of_occupancy_payment = DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["created_at"]
