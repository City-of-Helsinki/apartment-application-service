from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField

from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import ApplicationApartment
from customer.models import Customer

User = get_user_model()


class ApartmentReservation(models.Model):
    """
    Stores an applicant's reservation for the apartment.
    """

    apartment_uuid = models.UUIDField(verbose_name=_("apartment uuid"))
    customer = models.ForeignKey(
        Customer,
        verbose_name=_("customer"),
        on_delete=models.PROTECT,
        related_name="apartment_reservations",
    )
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
        max_length=32,
        default=ApartmentReservationState.SUBMITTED,
        verbose_name=_("apartment reservation state"),
    )

    class Meta:
        unique_together = [("apartment_uuid", "application_apartment")]

    @transaction.atomic
    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating:
            ApartmentReservationStateChangeEvent.objects.create(
                reservation=self, state=self.state
            )

    def set_state(
        self,
        state: ApartmentReservationState,
        user: User = None,
        comment: str = None,
    ) -> "ApartmentReservationStateChangeEvent":
        with transaction.atomic():
            if user and user.is_anonymous:
                # TODO this should be removed after proper authentication has been added
                user = None

            state_change_event = ApartmentReservationStateChangeEvent.objects.create(
                reservation=self, state=state, comment=comment or "", user=user
            )
            self.state = state
            self.save(update_fields=("state",))
            return state_change_event


class ApartmentQueueChangeEvent(models.Model):
    queue_application = models.ForeignKey(
        ApartmentReservation, models.CASCADE, related_name="queue_change_events"
    )
    type = EnumField(
        ApartmentQueueChangeEventType,
        max_length=15,
        verbose_name=_("change type"),
    )
    comment = models.CharField(_("comment"), max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


class ApartmentReservationStateChangeEvent(models.Model):
    reservation = models.ForeignKey(
        ApartmentReservation, models.CASCADE, related_name="state_change_events"
    )
    state = EnumField(
        ApartmentReservationState,
        max_length=32,
        verbose_name=_("apartment reservation state"),
    )
    comment = models.CharField(verbose_name=_("comment"), blank=True, max_length=255)
    timestamp = models.DateTimeField(verbose_name=_("timestamp"), auto_now_add=True)
    user = models.ForeignKey(
        User, verbose_name=_("user"), blank=True, null=True, on_delete=models.SET_NULL
    )
    cancellation_reason = EnumField(
        ApartmentReservationCancellationReason,
        max_length=32,
        verbose_name=_("cancellation reason"),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("id",)
