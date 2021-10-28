from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField
from pgcrypto.fields import (
    CharPGPPublicKeyField,
    DatePGPPublicKeyField,
    EmailPGPPublicKeyField,
    IntegerPGPPublicKeyField,
)
from uuid import uuid4

from apartment.models import Apartment
from apartment_application_service.fields import (
    BooleanPGPPublicKeyField,
    EnumPGPPublicKeyField,
    UUIDPGPPublicKeyField,
)
from apartment_application_service.models import TimestampedModel
from application_form.enums import (
    ApartmentQueueChangeEventType,
    ApplicationState,
    ApplicationType,
)
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

    profile = models.ForeignKey(Profile, null=True, on_delete=models.SET_NULL)
    apartments = models.ManyToManyField(
        Apartment,
        through="ApplicationApartment",
        blank=True,
        related_name="applications",
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
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, related_name="application_apartments"
    )
    priority_number = IntegerPGPPublicKeyField(_("priority number"))
    state = EnumField(
        ApplicationState,
        max_length=15,
        default=ApplicationState.SUBMITTED,
        verbose_name=_("application state"),
    )

    class Meta:
        unique_together = [("application", "priority_number")]


class ApartmentQueue(models.Model):
    apartment = models.OneToOneField(Apartment, models.CASCADE, related_name="queue")


class ApartmentQueueApplication(models.Model):
    queue = models.ForeignKey(
        ApartmentQueue, models.CASCADE, related_name="queue_applications"
    )
    queue_position = models.IntegerField(_("position in queue"))
    application_apartment = models.OneToOneField(
        ApplicationApartment, models.CASCADE, related_name="queue_application"
    )

    class Meta:
        unique_together = [("queue", "application_apartment")]


class ApartmentQueueChangeEvent(models.Model):
    queue_application = models.ForeignKey(
        ApartmentQueueApplication, models.CASCADE, related_name="change_events"
    )
    type = EnumField(
        ApartmentQueueChangeEventType,
        max_length=15,
        verbose_name=_("change type"),
    )
    comment = models.CharField(_("comment"), max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


class LotteryEvent(models.Model):
    apartment = models.ForeignKey(
        Apartment, models.PROTECT, related_name="lottery_events"
    )
    timestamp = models.DateTimeField(auto_now_add=True)


class LotteryEventResult(models.Model):
    event = models.ForeignKey(LotteryEvent, models.CASCADE, related_name="results")
    application_apartment = models.ForeignKey(
        ApplicationApartment, models.PROTECT, related_name="lottery_results"
    )
    result_position = models.IntegerField(_("result position"))

    class Meta:
        unique_together = [("event", "application_apartment")]
