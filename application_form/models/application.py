from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgcrypto.fields import (
    CharPGPPublicKeyField,
    DatePGPPublicKeyField,
    EmailPGPPublicKeyField,
    IntegerPGPPublicKeyField,
)
from uuid import uuid4

from apartment_application_service.fields import (
    BooleanPGPPublicKeyField,
    EnumPGPPublicKeyField,
    UUIDPGPPublicKeyField,
)
from apartment_application_service.models import TimestampedModel
from application_form.enums import ApplicationType
from customer.models import Customer
from users.models import Profile


class Application(TimestampedModel):
    external_uuid = UUIDPGPPublicKeyField(
        _("application identifier"), default=uuid4, editable=False
    )
    applicants_count = IntegerPGPPublicKeyField(_("applicants count"))
    type = EnumPGPPublicKeyField(
        ApplicationType, max_length=15, verbose_name=_("application type")
    )
    right_of_residence = IntegerPGPPublicKeyField(
        _("right of residence number"), null=True
    )
    has_children = BooleanPGPPublicKeyField(_("has children"), default=False)
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"), on_delete=models.CASCADE
    )
    submitted_late = models.BooleanField("submitted late", default=False)

    audit_log_id_field = "external_uuid"


class Applicant(TimestampedModel):
    first_name = CharPGPPublicKeyField(_("first name"), max_length=30)
    last_name = CharPGPPublicKeyField(_("last name"), max_length=150)
    email = EmailPGPPublicKeyField(_("email"))
    phone_number = CharPGPPublicKeyField(_("phone number"), max_length=40, null=False)
    street_address = CharPGPPublicKeyField(_("street address"), max_length=200)
    city = CharPGPPublicKeyField(_("city"), max_length=50)
    postal_code = CharPGPPublicKeyField(_("postal code"), max_length=10)
    age = IntegerPGPPublicKeyField(_("age"))
    date_of_birth = DatePGPPublicKeyField(_("date of birth"))
    ssn_suffix = CharPGPPublicKeyField(
        "personal identity code suffix",
        max_length=5,
        validators=[MinLengthValidator(5)],
    )
    contact_language = CharPGPPublicKeyField(
        _("contact language"),
        max_length=2,
        choices=Profile.CONTACT_LANGUAGE_CHOICES,
        null=True,
    )
    is_primary_applicant = BooleanPGPPublicKeyField(
        _("is primary applicant"), default=False
    )

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="applicants"
    )


class ApplicationApartment(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="application_apartments"
    )
    apartment_uuid = models.UUIDField(verbose_name=_("apartment uuid"))
    priority_number = IntegerPGPPublicKeyField(_("priority number"))

    class Meta:
        unique_together = [("application", "priority_number")]
