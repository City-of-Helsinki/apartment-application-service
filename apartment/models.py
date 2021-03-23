from django.db import models
from django.utils.translation import ugettext_lazy as _
from enumfields import EnumField
from simple_history.models import HistoricalRecords

from .enums import IdentifierScheme


class IdentifierScheme(models.Model):
    scheme_name = EnumField(IdentifierScheme, max_length=10)


class Identifier(models.Model):
    scheme = models.ForeignKey(IdentifierScheme, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=36)

    class Meta:
        unique_together = (
            "scheme",
            "identifier",
        )


class Project(models.Model):
    identifiers = models.ManyToManyField(Identifier)


class Apartment(models.Model):
    identifiers = models.ManyToManyField(Identifier)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    history = HistoricalRecords()
    is_available = models.BooleanField(default=True, verbose_name=_("is available"))

    def save(self, **kwargs):
        self.full_clean()
        return super(Apartment, self).save(**kwargs)
