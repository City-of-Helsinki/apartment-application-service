from typing import Optional

from django.db import models
from django.db.models import BooleanField, IntegerField
from django.utils.translation import gettext_lazy as _


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CommonApplicationData(models.Model):
    """Common fields used in Application, ApartmentReservation and Customer models."""

    is_right_of_occupancy_housing_changer = BooleanField(
        _("is right-of-occupancy housing changer"), blank=True, null=True
    )
    has_hitas_ownership = BooleanField(_("has HITAS ownership"), blank=True, null=True)
    right_of_residence = IntegerField(
        _("right of residence number"), blank=True, null=True
    )

    right_of_residence_is_old_batch = BooleanField(
        _("right of residence is old batch"),
        blank=True,
        null=True,
        help_text=_(
            "Only used when `right_of_residence` is set. When in use the default value "
            "is `false`. Value `true` means the right of residence number is granted "
            "on 31.8.2023 or before."
        ),
    )

    @property
    def right_of_residence_ordering_number(self) -> Optional[int]:
        """Get right of residence number to be used when calculating queue positions.

        This is a bit of a hack to make ordering logic more simple. The old batch of
        numbers need to be placed before the newer batch, so we add big enough constant
        number to the new batch's numbers to make sure that happens. This also maintain
        inner ordering inside both of the batches.
        """
        if self.right_of_residence is None:
            return None

        if self.right_of_residence_is_old_batch:
            return self.right_of_residence
        else:
            return self.right_of_residence + 100000000

    def save(self, *args, **kwargs):
        if self.right_of_residence is None:
            self.right_of_residence_is_old_batch = None
        elif self.right_of_residence_is_old_batch is None:
            # right_of_residence_is_old_batch default value is False
            self.right_of_residence_is_old_batch = False
        super().save(*args, **kwargs)

    class Meta:
        abstract = True
