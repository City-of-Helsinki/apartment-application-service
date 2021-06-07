from django.db import models
from django.utils.translation import ugettext_lazy as _
from enumfields import EnumField
from uuid import uuid4

from apartment.models import Apartment
from application_form.enums import ApplicationType
from users.models import Profile


class Application(models.Model):
    external_uuid = models.UUIDField(
        _("application identifier"), default=uuid4, editable=False
    )
    applicants_count = models.PositiveSmallIntegerField(_("applicants count"))
    type = EnumField(ApplicationType, max_length=15, verbose_name=_("application type"))
    right_of_residence = models.CharField(_("right of residence number"), max_length=10)
    has_children = models.BooleanField(_("has children"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    apartments = models.ManyToManyField(
        Apartment,
        through="ApplicationApartment",
        blank=True,
    )


class Applicant(models.Model):
    first_name = models.CharField(_("first name"), max_length=30)
    last_name = models.CharField(_("last name"), max_length=150)
    email = models.EmailField(_("email"))
    phone_number = models.CharField(_("phone number"), max_length=40, null=False)
    street_address = models.CharField(_("street address"), max_length=200)
    city = models.CharField(_("city"), max_length=50)
    postal_code = models.CharField(_("postal code"), max_length=10)
    age = models.PositiveSmallIntegerField(_("age"))
    contact_language = models.CharField(
        _("contact language"),
        max_length=2,
        choices=Profile.CONTACT_LANGUAGE_CHOICES,
        null=True,
    )
    is_primary_applicant = models.BooleanField(_("is primary applicant"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="applicants"
    )


class ApplicationApartment(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)
    priority_number = models.PositiveSmallIntegerField(_("priority number"))
