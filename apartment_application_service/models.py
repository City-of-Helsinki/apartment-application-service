from django.db import models
from django.utils.translation import gettext_lazy as _
from pgcrypto.fields import IntegerPGPPublicKeyField

from apartment_application_service.fields import BooleanPGPPublicKeyField


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CommonApplicationData(models.Model):
    """Common fields used in Application, ApartmentReservation and Customer models."""

    is_right_of_occupancy_housing_changer = BooleanPGPPublicKeyField(
        _("is right-of-occupancy housing changer"), blank=True, null=True
    )
    has_hitas_ownership = BooleanPGPPublicKeyField(
        _("has HITAS ownership"), blank=True, null=True
    )
    right_of_residence = IntegerPGPPublicKeyField(
        _("right of residence number"), blank=True, null=True
    )

    class Meta:
        abstract = True
