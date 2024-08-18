import logging
from uuid import uuid4

from django.conf import settings
from django.contrib import admin
from django.db import models
from django.db.models import UUIDField
from django.utils.translation import gettext_lazy as _
from helusers.models import AbstractUser
from pgcrypto.fields import CharPGPPublicKeyField, DatePGPPublicKeyField

from apartment_application_service.models import TimestampedModel
from users.enums import Roles

_logger = logging.getLogger(__name__)


class User(AbstractUser):
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    @admin.display(boolean=True)
    def is_django_salesperson(self):
        return self.groups.filter(name__iexact=Roles.DJANGO_SALESPERSON.name).exists()

    @admin.display(boolean=True)
    def is_drupal_salesperson(self):
        return self.groups.filter(name__iexact=Roles.DRUPAL_SALESPERSON.name).exists()

    @admin.display(boolean=True)
    def is_staff_user(self):
        return self.groups.filter(name__iexact=Roles.STAFF.name).exists()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def profile_or_user_first_name(self):
        return self._get_profile_or_user_field("first_name")

    @property
    def profile_or_user_last_name(self):
        return self._get_profile_or_user_field("last_name")

    @property
    def profile_or_user_email(self):
        return self._get_profile_or_user_field("email")

    @property
    def profile_or_user_full_name(self):
        return self._get_profile_or_user_field("full_name")

    def _get_profile_or_user_field(self, field_name):
        try:
            return getattr(self.profile, field_name)
        except Profile.DoesNotExist:
            return getattr(self, field_name)


class Profile(TimestampedModel):
    CONTACT_LANGUAGE_CHOICES = [
        ("fi", _("Finnish")),
        ("sv", _("Swedish")),
        ("en", _("English")),
    ]

    id = UUIDField(
        _("user identifier"), primary_key=True, default=uuid4, editable=False
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    first_name = models.CharField(_("first name"), max_length=30, blank=True)
    middle_name = models.CharField(
        _("middle name"), max_length=30, blank=True, null=True
    )
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    calling_name = models.CharField(
        _("calling name"), max_length=50, blank=True, null=True
    )
    email = models.CharField(
        max_length=254, verbose_name=_("email address"), blank=True
    )
    phone_number = models.CharField(_("phone number"), max_length=40)
    phone_number_nightly = models.CharField(
        _("phone number nightly"), max_length=50, blank=True, null=True
    )
    street_address = models.CharField(_("street address"), max_length=200)

    date_of_birth = DatePGPPublicKeyField(_("date of birth"))
    national_identification_number = CharPGPPublicKeyField(
        _("national identification number"),
        max_length=11,
        blank=True,
        null=True,
    )
    city = models.CharField(_("city"), max_length=50)
    postal_code = models.CharField(_("postal code"), max_length=10)
    contact_language = models.CharField(
        _("contact language"),
        max_length=2,
        choices=CONTACT_LANGUAGE_CHOICES,
    )

    @property
    def ssn_suffix(self):
        if self.national_identification_number:
            return self.national_identification_number[6:]
        return None

    @ssn_suffix.setter
    def ssn_suffix(self, value):
        prefix = ""
        if self.date_of_birth:
            prefix = self.date_of_birth.strftime("%d%m%y")
        elif self.national_identification_number:
            prefix = self.national_identification_number[:6]
        if len(prefix) != 6:
            prefix = "000000"
        self.national_identification_number = prefix + value

    def delete(self, *args, **kwargs):
        pk = self.pk
        _logger.info(f"Deleting profile {pk}")
        if self.user:
            self.user.delete()
        result = super().delete(*args, **kwargs)
        _logger.info(f"Profile {pk} deleted")
        return result

    def save(self, *args, update_fields=None, **kwargs):
        if update_fields and "ssn_suffix" in update_fields:
            update_fields = list(update_fields)
            update_fields.remove("ssn_suffix")
            update_fields.append("national_identification_number")
        super(Profile, self).save(*args, update_fields=update_fields, **kwargs)

    def is_salesperson(self):
        return self.user.is_drupal_salesperson()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


"""
Proxy models to be used in Django-admin
"""


class DrupalUser(User):
    class Meta:
        proxy = True


class DjangoUser(User):
    class Meta:
        proxy = True
