from django.db import models, transaction
from django.db.models import UniqueConstraint
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField

from application_form.models import ApartmentReservation
from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
)
from invoicing.utils import (
    generate_reference_number,
    get_euros_from_cents,
    get_rounded_price,
)


class InstallmentBase(models.Model):
    created_at = models.DateTimeField(
        verbose_name=_("created at"), default=now, editable=False
    )
    type = EnumField(InstallmentType, verbose_name=_("type"), max_length=32)
    value = models.DecimalField(
        verbose_name=_("value"), max_digits=16, decimal_places=2
    )
    account_number = models.CharField(max_length=255, verbose_name=_("account number"))
    due_date = models.DateField(verbose_name=_("due date"), blank=True, null=True)

    class Meta:
        abstract = True


class ApartmentInstallment(InstallmentBase):
    apartment_reservation = models.ForeignKey(
        ApartmentReservation,
        verbose_name=_("apartment reservation"),
        related_name="apartment_installments",
        on_delete=models.PROTECT,
    )
    reference_number = models.CharField(
        max_length=64, verbose_name=_("reference number"), unique=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["apartment_reservation", "type"], name="unique_reservation_type"
            )
        ]

    def set_reference_number(self, force=False):
        if self.reference_number and not force:
            return

        self.reference_number = generate_reference_number(self.id)
        self.save(update_fields=("reference_number",))

    @transaction.atomic
    def save(self, *args, **kwargs):
        creating = not self.id
        super().save(*args, **kwargs)

        if creating and not self.reference_number:
            self.set_reference_number()


class ProjectInstallmentTemplate(InstallmentBase):
    project_uuid = models.UUIDField(verbose_name=_("project UUID"))
    unit = EnumField(InstallmentUnit, verbose_name=_("unit"), max_length=32)
    percentage_specifier = EnumField(
        InstallmentPercentageSpecifier,
        verbose_name=_("percentage specifier"),
        max_length=32,
        blank=True,
        null=True,
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["project_uuid", "type"], name="unique_project_type"
            )
        ]

    def get_amount(self):
        return self.value if self.unit == InstallmentUnit.EURO else None

    def get_percentage(self):
        return self.value if self.unit == InstallmentUnit.PERCENT else None

    def get_corresponding_apartment_installment(self, apartment_data):
        apartment_installment = ApartmentInstallment()

        field_names = [
            f.name for f in InstallmentBase._meta.get_fields() if f.name != "created_at"
        ]
        for field_name in field_names:
            setattr(apartment_installment, field_name, getattr(self, field_name))

        if self.unit == InstallmentUnit.PERCENT:
            if not self.percentage_specifier:
                raise ValueError(
                    f"Cannot calculate apartment installment value, {self} "
                    f"has no percentage_specifier"
                )
            if self.percentage_specifier == InstallmentPercentageSpecifier.SALES_PRICE:
                price_in_cents = apartment_data["sales_price"]
            else:
                price_in_cents = apartment_data["debt_free_sales_price"]

            price = get_euros_from_cents(price_in_cents)
            percentage_multiplier = self.value / 100
            apartment_installment.value = get_rounded_price(
                price * percentage_multiplier
            )
        else:
            apartment_installment.value = self.value

        return apartment_installment
