"""
Customer models.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils.translation import gettext_lazy as _
from pgcrypto.fields import DatePGPPublicKeyField, TextPGPPublicKeyField

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
        if (
            not self.secondary_profile
            and self.__class__.objects.exclude(id=self.id)
            .filter(primary_profile=self.primary_profile)
            .exists()
        ):
            raise ValidationError(
                _("There already exists a Customer for the primary profile.")
            )
