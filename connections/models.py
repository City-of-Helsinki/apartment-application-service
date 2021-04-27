from django.db import models


class MappedApartment(models.Model):
    apartment_uuid = models.UUIDField(primary_key=True)
    mapped_etuovi = models.BooleanField(null=True)
    mapped_oikotie = models.BooleanField(null=True)
