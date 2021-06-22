from django.db import models
from pgcrypto import PGP_PUB_ENCRYPT_SQL_WITH_NULLIF
from pgcrypto.mixins import PGPPublicKeyFieldMixin


class UUIDPGPPublicKeyField(PGPPublicKeyFieldMixin, models.UUIDField):
    """UUID PGP public key encrypted field."""

    encrypt_sql = PGP_PUB_ENCRYPT_SQL_WITH_NULLIF
    cast_type = "UUID"
