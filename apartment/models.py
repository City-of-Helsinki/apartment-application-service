from django.db import models
from django.utils.translation import gettext_lazy as _

from apartment_application_service.models import TimestampedModel


class ProjectExtraData(TimestampedModel):
    """Project related data that is stored in Django side."""

    project_uuid = models.UUIDField(verbose_name=_("project UUID"), unique=True)
    offer_message_intro = models.TextField(
        verbose_name=_("offer message intro"), blank=True
    )
    offer_message_content = models.TextField(
        verbose_name=_("offer message content"), blank=True
    )
