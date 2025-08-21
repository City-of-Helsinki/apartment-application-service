"""
Customer models.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils.translation import gettext_lazy as _

from apartment_application_service.models import CommonApplicationData, TimestampedModel
from users.models import Profile

User = get_user_model()


class Customer(TimestampedModel, CommonApplicationData):
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

    additional_information = models.TextField(_("additional information"), blank=True)
    last_contact_date = models.DateField(_("last contact date"), blank=True, null=True)
    has_children = models.BooleanField(_("has children"), blank=True, null=True)
    is_age_over_55 = models.BooleanField(_("is age over 55"), blank=True, null=True)

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


class CustomerComment(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("customer"),
    )
    author = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        related_name="customer_comments",
        verbose_name=_("author"),
        null=True,
        blank=True,
    )
    author_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="customer_comments",
        verbose_name=_("author user"),
        null=True,
        blank=True,
    )
    content = models.TextField(_("comment content"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.customer} | {self.display_author_name}: {self.content[:20]}"

    @property
    def display_author_name(self) -> str:
        if self.author_user:
            full = f"{self.author_user.first_name} {self.author_user.last_name}".strip()
            return full or (self.author_user.username or self.author_user.email or "—")
        if self.author:
            return getattr(self.author, "full_name", "") or "—"
        return "—"
