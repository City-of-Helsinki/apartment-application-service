from django.db import models
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField

from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationState,
)
from application_form.models import ApplicationApartment


class ApartmentReservation(models.Model):
    """
    Stores an applicant's reservation for the apartment.
    """

    apartment_uuid = models.UUIDField(verbose_name=_("apartment uuid"))
    queue_position = models.IntegerField(_("position in queue"))
    application_apartment = models.OneToOneField(
        ApplicationApartment,
        models.CASCADE,
        related_name="apartment_reservation",
        null=True,
        blank=True,
    )
    state = EnumField(
        ApartmentReservationState,
        max_length=15,
        default=ApartmentReservationState.SUBMITTED,
        verbose_name=_("apartment reservation state"),
    )

    class Meta:
        unique_together = [("apartment_uuid", "application_apartment")]


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
