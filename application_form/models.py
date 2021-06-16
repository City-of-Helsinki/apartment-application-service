from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from enumfields import EnumField
from uuid import uuid4

from apartment.models import Apartment
from apartment_application_service.models import TimestampedModel
from application_form.enums import ApplicationType
from users.models import Profile


class Application(TimestampedModel):
    external_uuid = models.UUIDField(
        _("application identifier"), default=uuid4, editable=False
    )
    applicants_count = models.PositiveSmallIntegerField(_("applicants count"))
    type = EnumField(ApplicationType, max_length=15, verbose_name=_("application type"))
    right_of_residence = models.CharField(
        _("right of residence number"), max_length=10, null=True
    )
    has_children = models.BooleanField(_("has children"), default=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    apartments = models.ManyToManyField(
        Apartment,
        through="ApplicationApartment",
        blank=True,
    )

    audit_log_id_field = "external_uuid"


class Applicant(TimestampedModel):
    first_name = models.CharField(_("first name"), max_length=30)
    last_name = models.CharField(_("last name"), max_length=150)
    email = models.EmailField(_("email"))
    phone_number = models.CharField(_("phone number"), max_length=40, null=False)
    street_address = models.CharField(_("street address"), max_length=200)
    city = models.CharField(_("city"), max_length=50)
    postal_code = models.CharField(_("postal code"), max_length=10)
    age = models.PositiveSmallIntegerField(_("age"))
    date_of_birth = models.DateField(_("date of birth"))
    ssn_suffix = models.CharField(
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
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)
    priority_number = models.PositiveSmallIntegerField(_("priority number"))
