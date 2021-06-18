from django.db import models

from apartment_application_service.models import TimestampedModel


class MappedApartment(TimestampedModel):
    """
    Model class for saving data on succsesfully mapped apartments by
    Oikotie and Etuovi mappers.
    """

    apartment_uuid = models.UUIDField(primary_key=True)
    mapped_etuovi = models.BooleanField(default=False)
    mapped_oikotie = models.BooleanField(default=False)
