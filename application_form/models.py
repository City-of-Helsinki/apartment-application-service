from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import ugettext_lazy as _

CURRENT_HOUSING_CHOICES = [
    ("Omistusasunto", "Omistusasunto"),
    ("Vuokra-asunto", "Vuokra-asunto"),
    ("Asumisoikeusasunto", "Asumisoikeusasunto"),
    ("Muu", "Muu"),
]

PERMISSIONS_LIST = [
    ("add", _("Can add new applications.")),
    ("change", _("Can change the existing applications.")),
    ("delete", _("Can remove remove the existing applications.")),
]


class HasoApplication(models.Model):
    running_number = models.CharField(max_length=255, verbose_name=_("running number"))
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
    is_over_55 = models.BooleanField(default=False, verbose_name=_("is over 55"))
    project_uuid = models.UUIDField(verbose_name=_("project uuid"))
    apartment_uuids = ArrayField(models.UUIDField(), verbose_name=_("apartment uuids"))

    class Meta:
        permissions = PERMISSIONS_LIST


class HitasApplication(models.Model):
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
        permissions = PERMISSIONS_LIST
