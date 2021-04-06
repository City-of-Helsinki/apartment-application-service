from django.db import models
from django.utils.translation import ugettext_lazy as _


class Customer(models.Model):
    hel_profile_uuid = models.UUIDField(verbose_name=_("helsinki profile uuid"))
    drupal_customer_id = models.IntegerField(verbose_name=_("drupal customer id"))
    first_name = models.CharField(
        max_length=50,
        verbose_name=_("first name"),
        blank=True,
    )
    last_name = models.CharField(
        max_length=50,
        verbose_name=_("last name"),
        blank=True,
    )
    email = models.CharField(max_length=255, verbose_name=_("email"), blank=True)
    authorized = models.BooleanField(verbose_name=_("authorized"))
