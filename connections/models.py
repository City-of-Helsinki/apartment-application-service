from django.db import models

from apartment_application_service.models import TimestampedModel


class MappedApartment(TimestampedModel):
    """
    Model class for saving data on succsesfully mapped apartments by
    Oikotie and Etuovi mappers.

    Keeps a list of apartments that are currently mapped to Etuovi and Oikotie.

    mapped_etuovi and mapped_oikotie are set to True when the apartment is added
    to the export XML file and then set to False when the apartment is left out from
    an export XML file. If an apartment is left out from an export XML file,
    Etuovi or Oikotie will remove it from their system.

    Meaning this model is the source of truth for which apartments should be visible
    at Etuovi and Oikotie.
    """

    apartment_uuid = models.UUIDField(primary_key=True)
    mapped_etuovi = models.BooleanField(default=False)
    mapped_oikotie = models.BooleanField(default=False)
    last_mapped_to_etuovi = models.DateTimeField(null=True, blank=True)
    last_mapped_to_oikotie = models.DateTimeField(null=True, blank=True)
