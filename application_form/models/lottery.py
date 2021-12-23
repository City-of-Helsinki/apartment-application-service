from django.db import models
from django.utils.translation import gettext_lazy as _

from apartment.models import Apartment
from application_form.models.application import ApplicationApartment


class LotteryEvent(models.Model):
    apartment = models.ForeignKey(
        Apartment, models.PROTECT, related_name="lottery_events"
    )
    timestamp = models.DateTimeField(auto_now_add=True)


class LotteryEventResult(models.Model):
    event = models.ForeignKey(LotteryEvent, models.CASCADE, related_name="results")
    application_apartment = models.OneToOneField(ApplicationApartment, models.PROTECT)
    result_position = models.IntegerField(_("result position"))

    class Meta:
        unique_together = [("event", "application_apartment")]
