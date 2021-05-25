from django.db import models
from django.utils.translation import ugettext_lazy as _
from enumfields import EnumField
from uuid import uuid4

from application_form.enums import (
    ApplicationState,
    ApplicationType,
    AttachmentType,
    FileFormat,
)
from users.models import Profile


class Application(models.Model):
    id = models.UUIDField(
        _("application identifier"), primary_key=True, default=uuid4, editable=False
    )
    applicants_count = models.PositiveSmallIntegerField(_("applicants count"))
    type = EnumField(ApplicationType, max_length=15, verbose_name=_("application type"))
    state = EnumField(
        ApplicationState,
        max_length=15,
        default=ApplicationState.SUBMITTED,
        verbose_name=_("application state"),
    )
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)


class Applicant(models.Model):
    first_name = models.CharField(_("first name"), max_length=30)
    last_name = models.CharField(_("last name"), max_length=150)
    email = models.EmailField(_("email"))
    has_children = models.BooleanField(_("has children"), default=False)
    age = models.PositiveSmallIntegerField(_("age"))
    is_primary_applicant = models.BooleanField(_("is primary applicant"), default=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)


class File(models.Model):
    id = models.UUIDField(
        _("file identifier"), primary_key=True, default=uuid4, editable=False
    )
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    attachment_name = EnumField(
        AttachmentType, max_length=15, verbose_name=_("attachment name")
    )
    file_name = models.CharField(_("file name"), max_length=150)
    location_id = models.CharField(_("location path"), max_length=150)
    file_format = EnumField(
        FileFormat, max_length=15, verbose_name=_("filename extension")
    )
    # awaiting definition
    other_metadata = models.JSONField()
