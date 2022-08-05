from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField
from pgcrypto.fields import CharPGPPublicKeyField

from apartment_application_service.models import TimestampedModel
from application_form.enums import OfferState
from application_form.models.reservation import ApartmentReservation

User = get_user_model()


class OfferQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            Q(state=OfferState.ACCEPTED)
            | Q(Q(state=OfferState.PENDING) & Q(valid_until__gte=timezone.localdate()))
        )


class Offer(TimestampedModel):
    apartment_reservation = models.OneToOneField(
        ApartmentReservation,
        verbose_name=_("apartment reservation"),
        on_delete=models.PROTECT,
        related_name="offer",
    )
    valid_until = models.DateField(verbose_name=_("valid until"))
    state = EnumField(OfferState, verbose_name=_("state"), default=OfferState.PENDING)
    concluded_at = models.DateTimeField(
        verbose_name=_("concluded at"), null=True, blank=True
    )
    comment = models.TextField(verbose_name=_("comment"), blank=True)

    objects = OfferQuerySet.as_manager()
    # Metadata fields
    handler = CharPGPPublicKeyField(
        verbose_name=_("handler"), max_length=200, blank=True
    )

    class Meta:
        ordering = ("id",)

    @property
    def is_expired(self) -> bool:
        return (
            self.state == OfferState.PENDING and timezone.localdate() > self.valid_until
        )
