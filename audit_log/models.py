from django.contrib.postgres.fields import JSONField
from django.db import models


class AuditLog(models.Model):
    message = JSONField()
