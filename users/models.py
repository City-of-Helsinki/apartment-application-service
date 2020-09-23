from django.utils.translation import ugettext_lazy as _
from helusers.models import AbstractUser


class User(AbstractUser):
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
