from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import ugettext_lazy as _

CURRENT_HOUSING_CHOICES = [
    ("Omistusasunto", "Omistusasunto"),
    ("Vuokra-asunto", "Vuokra-asunto"),
    ("Asumisoikeusasunto", "Asumisoikeusasunto"),
    ("Muu", "Muu"),
]

HASO_PERMISSIONS_LIST = [
    ("haso_create", _("Can create new haso applications.")),
    ("haso_update", _("Can update the existing haso applications.")),
    ("haso_delete", _("Can remove remove the existing haso applications.")),
]

HITAS_PERMISSIONS_LIST = [
    ("hitas_create", _("Can create new hitas applications.")),
    ("hitas_update", _("Can update the existing hitas applications.")),
    ("hitas_delete", _("Can remove remove the existing hitas applications.")),
]


class ApplicationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            is_accepted=False, is_rejected=False, applicant_has_accepted_offer=False
        )


class ApplicationMixin(models.Model):
    is_approved = models.BooleanField(default=False, verbose_name=_("is accepted"))
    is_rejected = models.BooleanField(default=False, verbose_name=_("is rejected"))
    rejection_description = models.TextField(
        default="",
        verbose_name=_("rejection description"),
    )
    applicant_has_accepted_offer = models.BooleanField(
        default=False, verbose_name=_("applicant has accepted offer")
    )

    objects = ApplicationQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, **kwargs):
        if self.is_approved and self.is_rejected:
            raise ValueError(
                _("application cannot be accepted and rejected at the same time.")
            )
        if self.applicant_has_accepted_offer and not self.is_approved:
            raise ValueError(
                _("the offer cannot be accepted before the application is approved.")
            )
        super(ApplicationMixin, self).save(**kwargs)


class HasoApplication(ApplicationMixin):
    right_of_occupancy_id = models.CharField(
        max_length=255, verbose_name=_("right of occupancy ID")
    )
    current_housing = models.CharField(
        max_length=255,
        choices=CURRENT_HOUSING_CHOICES,
        verbose_name=_("current housing"),
    )
    housing_description = models.TextField(verbose_name=_("housing description"))
    housing_type = models.CharField(max_length=255, verbose_name=_("housing type"))
    housing_area = models.FloatField(verbose_name=_("housing area"))
    is_changing_occupancy_apartment = models.BooleanField(
        default=False, verbose_name=_("is changing occupancy apartment")
    )
    is_over_55 = models.BooleanField(
        default=False, verbose_name=_("is applicant over 55 years old")
    )
    project_uuid = models.UUIDField(verbose_name=_("project uuid"))
    apartment_uuids = ArrayField(models.UUIDField(), verbose_name=_("apartment uuids"))

    class Meta:
        permissions = HASO_PERMISSIONS_LIST


class HitasApplication(ApplicationMixin):
    has_previous_hitas_apartment = models.BooleanField(
        default=False, verbose_name=_("has previous hitas apartment")
    )
    previous_hitas_description = models.TextField(
        verbose_name=_("previous hitas descripiton")
    )
    has_children = models.BooleanField(default=False, verbose_name=_("has children"))
    project_uuid = models.UUIDField(verbose_name=_("project uuid"))
    apartment_uuid = models.UUIDField(verbose_name=_("apartment uuid"))

    class Meta:
        permissions = HITAS_PERMISSIONS_LIST
