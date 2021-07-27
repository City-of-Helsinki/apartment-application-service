import logging
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from helusers.models import AbstractUser
from pgcrypto.fields import (
    CharPGPPublicKeyField,
    DatePGPPublicKeyField,
    EmailPGPPublicKeyField,
)
from uuid import uuid4

from apartment_application_service.fields import UUIDPGPPublicKeyField
from apartment_application_service.models import TimestampedModel

_logger = logging.getLogger(__name__)


class User(AbstractUser):
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")


class Profile(TimestampedModel):
    CONTACT_LANGUAGE_CHOICES = [
        ("fi", _("Finnish")),
        ("sv", _("Swedish")),
        ("en", _("English")),
    ]

    id = UUIDPGPPublicKeyField(
        _("user identifier"), primary_key=True, default=uuid4, editable=False
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False
    )
    first_name = CharPGPPublicKeyField(_("first name"), max_length=30, blank=True)
    last_name = CharPGPPublicKeyField(_("last name"), max_length=150, blank=True)
    email = EmailPGPPublicKeyField(_("email address"), blank=True)
    phone_number = CharPGPPublicKeyField(_("phone number"), max_length=40, null=False)
    street_address = CharPGPPublicKeyField(_("street address"), max_length=200)
    date_of_birth = DatePGPPublicKeyField(_("date of birth"))
    city = CharPGPPublicKeyField(_("city"), max_length=50)
    postal_code = CharPGPPublicKeyField(_("postal code"), max_length=10)
    contact_language = CharPGPPublicKeyField(
        _("contact language"),
        max_length=2,
        choices=CONTACT_LANGUAGE_CHOICES,
    )

    def delete(self, *args, **kwargs):
        pk = self.pk
        _logger.info(f"Deleting profile {pk}")
        self.user.delete()
        result = super().delete(*args, **kwargs)
        _logger.info(f"Profile {pk} deleted")
        return result

    def __str__(self):
        return str(self.user)

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")
