import uuid
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Deferrable, UniqueConstraint
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField
from pgcrypto.fields import BooleanPGPPublicKeyField, CharPGPPublicKeyField

from apartment_application_service.models import CommonApplicationData
from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
)
from application_form.models import ApplicationApartment
from audit_log import audit_logging
from audit_log.enums import Operation
from customer.models import Customer

User = get_user_model()


class ApartmentReservationQuerySet(models.QuerySet):
    def reserved(self):
        return self.exclude(
            state__in=(
                ApartmentReservationState.SUBMITTED,
                ApartmentReservationState.CANCELED,
            )
        )

    def related_fields(self):
        return (
            self.select_related("offer")
            .select_related("customer")
            .select_related("customer__primary_profile")
            .select_related("customer__secondary_profile")
            .select_related("application_apartment")
            .select_related("application_apartment__lotteryeventresult")
            .select_related("revaluation")
        )

    def active(self):
        return self.exclude(state=ApartmentReservationState.CANCELED)

    def first_in_queue(
        self, apartment_uuid: uuid.UUID
    ) -> Optional["ApartmentReservation"]:
        try:
            return (
                self.active()
                .filter(apartment_uuid=apartment_uuid)
                .earliest("queue_position")
            )
        except ApartmentReservation.DoesNotExist:
            return None


class ApartmentReservation(CommonApplicationData):
    """
    Stores an applicant's reservation for the apartment.
    """

    apartment_uuid = models.UUIDField(verbose_name=_("apartment uuid"), db_index=True)
    customer = models.ForeignKey(
        Customer,
        verbose_name=_("customer"),
        on_delete=models.PROTECT,
        related_name="apartment_reservations",
    )
    queue_position = models.IntegerField(
        verbose_name=_("position in queue"), null=True, blank=True
    )
    list_position = models.IntegerField(_("position in list"))
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
    has_children = BooleanPGPPublicKeyField(_("has children"), blank=True, null=True)
    is_age_over_55 = BooleanPGPPublicKeyField(
        _("is age over 55"), blank=True, null=True
    )
    # Metadata fields
    handler = CharPGPPublicKeyField(
        verbose_name=_("handler"), max_length=200, blank=True
    )
    submitted_late = models.BooleanField("submitted late", default=False)
    objects = ApartmentReservationQuerySet.as_manager()

    class Meta:
        unique_together = [("apartment_uuid", "application_apartment")]
        constraints = [
            UniqueConstraint(
                name="apt_uuid_list_pos_unq_def_const",
                fields=["apartment_uuid", "list_position"],
                deferrable=Deferrable.DEFERRED,
            )
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        creating = self._state.adding
        user = kwargs.pop("user", None)
        super().save(*args, **kwargs)
        if creating:
            ApartmentReservationStateChangeEvent.objects.create(
                reservation=self, state=self.state, user=user
            )

    @transaction.atomic
    def set_state(
        self,
        state: ApartmentReservationState,
        user: User = None,
        comment: str = None,
        cancellation_reason: ApartmentReservationCancellationReason = None,
        replaced_by: "ApartmentReservation" = None,
    ) -> "ApartmentReservationStateChangeEvent":
        if cancellation_reason and state != ApartmentReservationState.CANCELED:
            raise ValidationError(
                "cancellation_reason cannot be set when state is not canceled."
            )

        state_change_event = ApartmentReservationStateChangeEvent.objects.create(
            reservation=self,
            state=state,
            comment=comment or "",
            user=user,
            cancellation_reason=cancellation_reason,
            replaced_by=replaced_by,
        )
        self.state = state
        self.save(update_fields=("state",))
        audit_logging.log(user, operation=Operation.CREATE, target=state_change_event)
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
    replaced_by = models.ForeignKey(
        ApartmentReservation,
        verbose_name=_("replaced by"),
        related_name="replaced_reservation_state_change_events",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ("id",)
