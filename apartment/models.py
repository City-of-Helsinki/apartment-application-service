from django.db import models
from django.utils.translation import ugettext_lazy as _
from enumfields import EnumField

from .enums import IdentifierSchemaType


class Project(models.Model):
    street_address = models.CharField(_("street address"), max_length=200)


class Apartment(models.Model):
    street_address = models.CharField(_("street address"), max_length=200)
    apartment_number = models.CharField(_("apartment number"), max_length=10)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="apartments"
    )


class Identifier(models.Model):
    schema_type = EnumField(IdentifierSchemaType, max_length=10)
    identifier = models.CharField(max_length=36)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, related_name="identifiers"
    )
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, null=True, related_name="identifiers"
    )

    class Meta:
        unique_together = (
            "schema_type",
            "identifier",
        )
