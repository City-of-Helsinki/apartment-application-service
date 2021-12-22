from django.db import models
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField

from apartment.models import Apartment
from application_form.enums import ApartmentQueueChangeEventType
from application_form.models import ApplicationApartment


class ApartmentReservation(models.Model):
    """
    Stores an applicant's reservation for the apartment.
    """

    apartment = models.ForeignKey(
        Apartment, models.PROTECT, "queue_applications", blank=True, null=True
    )
    queue_position = models.IntegerField(_("position in queue"))
    application_apartment = models.OneToOneField(
        ApplicationApartment, models.CASCADE, related_name="queue_application"
    )

    class Meta:
        unique_together = [("apartment", "application_apartment")]


class ApartmentQueueChangeEvent(models.Model):
    queue_application = models.ForeignKey(
        ApartmentReservation, models.CASCADE, related_name="change_events"
    )
    type = EnumField(
        ApartmentQueueChangeEventType,
        max_length=15,
        verbose_name=_("change type"),
    )
    comment = models.CharField(_("comment"), max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
