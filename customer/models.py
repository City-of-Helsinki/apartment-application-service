"""
Customer models.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgcrypto.fields import DatePGPPublicKeyField, TextPGPPublicKeyField

from apartment_application_service.models import TimestampedModel
from users.models import Profile


class Customer(TimestampedModel):
    """
    Customer information.
    """

    profiles = models.ManyToManyField(Profile)

    additional_information = TextPGPPublicKeyField(
        _("additional information"), blank=True
    )
    last_contact_date = DatePGPPublicKeyField(
        _("last contact date"), blank=True, null=True
    )

    def __str__(self):
        return ", ".join([str(profile) for profile in self.profiles.all()])
