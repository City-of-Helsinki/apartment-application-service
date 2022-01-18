from django.db import models
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField

from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
)


class InstallmentBase(models.Model):
    created_at = models.DateTimeField(verbose_name=_("created at"), auto_now_add=True)
    type = EnumField(InstallmentType, verbose_name=_("type"), max_length=32)
    value = models.DecimalField(
        verbose_name=_("value"), max_digits=16, decimal_places=2
    )
    unit = EnumField(InstallmentUnit, verbose_name=_("unit"), max_length=32)
    percentage_specifier = EnumField(
        InstallmentPercentageSpecifier,
        verbose_name=_("percentage specifier"),
        max_length=32,
        blank=True,
        null=True,
    )
    account_number = models.CharField(max_length=255, verbose_name=_("account number"))
    due_date = models.DateField(verbose_name=_("due date"), blank=True, null=True)

    class Meta:
        abstract = True

    def get_amount(self):
        return self.value if self.unit == InstallmentUnit.EURO else None

    def get_percentage(self):
        return self.value if self.unit == InstallmentUnit.PERCENT else None


class ProjectInstallmentTemplate(InstallmentBase):
    project_uuid = models.UUIDField(verbose_name=_("project UUID"))


class ApartmentInstallment(InstallmentBase):
    apartment_uuid = models.UUIDField(verbose_name=_("apartment UUID"))
    reference_number = models.CharField(
        max_length=64, verbose_name=_("reference number"), blank=True
    )
