"""
Customer models.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils.translation import gettext_lazy as _
from pgcrypto.fields import (
    BooleanPGPPublicKeyField,
    DatePGPPublicKeyField,
    IntegerPGPPublicKeyField,
    TextPGPPublicKeyField,
)

from apartment_application_service.models import TimestampedModel
from users.models import Profile


class Customer(TimestampedModel):
    """
    Customer information.
    """

    primary_profile = models.ForeignKey(
        Profile,
        verbose_name=_("primary profile"),
        related_name="customers_where_primary",
        on_delete=models.PROTECT,
    )
    secondary_profile = models.ForeignKey(
        Profile,
        verbose_name=_("secondary profile"),
        related_name="customers_where_secondary",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    additional_information = TextPGPPublicKeyField(
        _("additional information"), blank=True
    )
    last_contact_date = DatePGPPublicKeyField(
        _("last contact date"), blank=True, null=True
    )
    has_children = BooleanPGPPublicKeyField(_("has children"), blank=True, null=True)
    has_hitas_ownership = BooleanPGPPublicKeyField(
        _("has hitas ownership"), blank=True, null=True
    )
    is_age_over_55 = BooleanPGPPublicKeyField(
        _("is age over 55"), blank=True, null=True
    )
    is_right_of_occupancy_housing_changer = BooleanPGPPublicKeyField(
        _("is right-of-occupancy housing changer"), blank=True, null=True
    )
    right_of_residence = IntegerPGPPublicKeyField(
        _("right of residence number"), blank=True, null=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["primary_profile", "secondary_profile"],
                name="customer_primary_profile_secondary_profile_unique",
            ),
            models.UniqueConstraint(
                name="customer_sole_primary_profile_unique",
                fields=("primary_profile",),
                condition=Q(secondary_profile__isnull=True),
            ),
        ]

    def __str__(self):
        return ", ".join(
            [str(p) for p in [self.primary_profile, self.secondary_profile] if p]
        )

    def clean(self):
        if self.__class__.objects.exclude(id=self.id).filter(
            primary_profile=self.primary_profile,
            secondary_profile=self.secondary_profile,
        ):
            raise ValidationError(
                _(
                    "There already exists a Customer which has the same primary and "
                    "secondary profile."
                )
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
