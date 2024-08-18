from uuid import uuid4

from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField
from pgcrypto.fields import CharPGPPublicKeyField, DatePGPPublicKeyField

from apartment_application_service.models import CommonApplicationData, TimestampedModel
from application_form.enums import ApplicationArrivalMethod, ApplicationType
from customer.models import Customer
from users.models import Profile


class Application(TimestampedModel, CommonApplicationData):
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"), on_delete=models.CASCADE
    )
    external_uuid = models.UUIDField(
        _("application identifier"), default=uuid4, editable=False
    )

    applicants_count = models.IntegerField(_("applicants count"))
    type = EnumField(ApplicationType, max_length=15, verbose_name=_("application type"))
    has_children = models.BooleanField(_("has children"), default=False)

    submitted_late = models.BooleanField("submitted late", default=False)

    # Metadata fields
    process_number = models.CharField(_("process number"), max_length=32)
    handler_information = models.CharField(_("handler information"), max_length=100)
    method_of_arrival = EnumField(
        ApplicationArrivalMethod,
        max_length=50,
        verbose_name=_("method of arrival"),
        default=ApplicationArrivalMethod.ELECTRONICAL_SYSTEM,
    )
    sender_names = models.CharField(_("sender names"), max_length=200)

    audit_log_id_field = "external_uuid"


class Applicant(TimestampedModel):
    first_name = models.CharField(_("first name"), max_length=30)
    last_name = models.CharField(_("last name"), max_length=150)
    email = models.EmailField(_("email"))
    phone_number = models.CharField(_("phone number"), max_length=40)
    street_address = models.CharField(_("street address"), max_length=200)
    city = models.CharField(_("city"), max_length=50)
    postal_code = models.CharField(_("postal code"), max_length=10)
    age = models.IntegerField(_("age"))
    date_of_birth = DatePGPPublicKeyField(_("date of birth"))
    ssn_suffix = CharPGPPublicKeyField(
        "personal identity code suffix",
        max_length=5,
        validators=[MinLengthValidator(5)],
    )
    contact_language = models.CharField(
        _("contact language"),
        max_length=2,
        choices=Profile.CONTACT_LANGUAGE_CHOICES,
        null=True,
    )
    is_primary_applicant = models.BooleanField(_("is primary applicant"), default=False)

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="applicants"
    )


class ApplicationApartment(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="application_apartments"
    )
    apartment_uuid = models.UUIDField(verbose_name=_("apartment uuid"))
    priority_number = models.IntegerField(_("priority number"))

    class Meta:
        unique_together = [("application", "priority_number")]
