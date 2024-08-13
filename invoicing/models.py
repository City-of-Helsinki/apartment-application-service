from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import UniqueConstraint
from django.utils import timezone
from django.utils.timezone import localdate, now
from django.utils.translation import gettext_lazy as _
from enumfields import EnumField
from typing_extensions import assert_never

from apartment_application_service.models import TimestampedModel
from application_form.models import ApartmentReservation
from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
    PaymentStatus,
    PriceRounding,
)
from invoicing.utils import (
    generate_reference_number,
    get_euros_from_cents,
    get_rounded_price,
)

User = get_user_model()


class AlreadyAddedToBeSentToSapError(Exception):
    pass


class InstallmentBase(models.Model):
    # we are not inheriting TimestampedModel because we want to be able to set values
    # for these manually to get exactly the same values for installments that are
    # created / updated on the same request
    created_at = models.DateTimeField(
        verbose_name=_("created at"), default=now, editable=False
    )
    updated_at = models.DateTimeField(
        verbose_name=_("updated at"), default=now, editable=False
    )

    type = EnumField(InstallmentType, verbose_name=_("type"), max_length=32)
    value = models.DecimalField(
        verbose_name=_("value"), max_digits=16, decimal_places=2
    )
    account_number = models.CharField(max_length=255, verbose_name=_("account number"))
    due_date = models.DateField(verbose_name=_("due date"), blank=True, null=True)

    class Meta:
        abstract = True

    def is_numbered_payment(self) -> bool:
        return self.type in {
            InstallmentType.PAYMENT_1,
            InstallmentType.PAYMENT_2,
            InstallmentType.PAYMENT_3,
            InstallmentType.PAYMENT_4,
            InstallmentType.PAYMENT_5,
            InstallmentType.PAYMENT_6,
            InstallmentType.PAYMENT_7,
        }


class ApartmentInstallmentQuerySet(models.QuerySet):
    def sending_to_sap_needed(self):
        max_due_date = timezone.localdate() + timedelta(
            days=settings.SAP_DAYS_UNTIL_INSTALLMENT_DUE_DATE
        )
        return self.filter(
            added_to_be_sent_to_sap_at__isnull=False,
            sent_to_sap_at__isnull=True,
            due_date__lt=max_due_date,
        )

    def set_sent_to_sap_at(self, dt: datetime = None):
        self.update(sent_to_sap_at=dt or timezone.now())


class ApartmentInstallment(InstallmentBase):
    MIN_INVOICE_NUMBER = 730000001
    MAX_INVOICE_NUMBER = 999999999

    apartment_reservation = models.ForeignKey(
        ApartmentReservation,
        verbose_name=_("apartment reservation"),
        related_name="apartment_installments",
        on_delete=models.PROTECT,
    )

    invoice_number = models.IntegerField(
        verbose_name=_("invoice number"),
        validators=[
            MinValueValidator(MIN_INVOICE_NUMBER),
            MaxValueValidator(MAX_INVOICE_NUMBER),
        ],
        unique=True,
    )
    reference_number = models.CharField(
        max_length=64, verbose_name=_("reference number"), unique=True
    )
    added_to_be_sent_to_sap_at = models.DateTimeField(
        verbose_name=_("added to be sent to SAP at"), null=True, blank=True
    )
    sent_to_sap_at = models.DateTimeField(
        verbose_name=_("sent to SAP at"), null=True, blank=True
    )

    handler = models.CharField(verbose_name=_("handler"), max_length=200, blank=True)

    objects = ApartmentInstallmentQuerySet.as_manager()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["apartment_reservation", "type"], name="unique_reservation_type"
            )
        ]

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or localdate() <= self.due_date:
            return False

        return (
            sum(
                payment.amount
                for payment in self.payments.filter(payment_date__lte=self.due_date)
            )
            < self.value
        )

    @property
    def payment_status(self) -> PaymentStatus:
        paid_amount = sum(payment.amount for payment in self.payments.all())
        if not paid_amount:
            return PaymentStatus.UNPAID
        elif paid_amount == self.value:
            return PaymentStatus.PAID
        elif paid_amount < self.value:
            return PaymentStatus.UNDERPAID
        else:
            return PaymentStatus.OVERPAID

    def _get_next_invoice_number(self):
        if self.invoice_number:
            return self.invoice_number

        apartment_installment = (
            ApartmentInstallment.objects.all().order_by("-invoice_number").first()
        )

        if apartment_installment:
            return apartment_installment.invoice_number + 1

        return self.MIN_INVOICE_NUMBER

    def set_reference_number(self, force=False):
        if self.reference_number and not force:
            return

        self.reference_number = generate_reference_number(self.id)
        self.save(update_fields=("reference_number",))

    @transaction.atomic
    def save(self, *args, **kwargs):
        creating = not self.id

        self.invoice_number = self._get_next_invoice_number()

        if creating:
            generate_reference_number = not self.reference_number

            if generate_reference_number:
                # set a temporary unique reference number to please the unique
                # constraint
                self.reference_number = str(f"TEMP-{uuid4()}")

            super().save(*args, **kwargs)

            if generate_reference_number:
                self.set_reference_number(force=True)
        else:
            super().save(*args, **kwargs)

    def add_to_be_sent_to_sap(self, force=False):
        if self.added_to_be_sent_to_sap_at and not force:
            raise AlreadyAddedToBeSentToSapError()
        self.added_to_be_sent_to_sap_at = timezone.now()
        self.save(update_fields=("added_to_be_sent_to_sap_at",))


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

    def get_corresponding_apartment_installment(
        self, apartment_data
    ) -> ApartmentInstallment:
        apartment_installment = ApartmentInstallment()

        field_names = [
            f.name for f in InstallmentBase._meta.get_fields() if f.name != "created_at"
        ]
        for field_name in field_names:
            setattr(apartment_installment, field_name, getattr(self, field_name))

        if self.unit == InstallmentUnit.EURO:
            return apartment_installment
        elif self.unit == InstallmentUnit.PERCENT:
            apartment_installment.value = self._get_value_from_percentage(
                apartment_data
            )
            return apartment_installment
        else:
            assert_never(self.unit)

    def _get_value_from_percentage(self, apartment_data) -> Decimal:
        ps: InstallmentPercentageSpecifier = self.percentage_specifier
        if ps == InstallmentPercentageSpecifier.SALES_PRICE_FLEXIBLE:
            # flexible payment's value will be populated later based on the other
            # installments of the same apartment
            return Decimal(0)
        elif ps == InstallmentPercentageSpecifier.SALES_PRICE:
            price_in_cents = apartment_data["sales_price"]
        elif ps == InstallmentPercentageSpecifier.DEBT_FREE_SALES_PRICE:
            price_in_cents = apartment_data["debt_free_sales_price"]
        elif ps == InstallmentPercentageSpecifier.RIGHT_OF_OCCUPANCY_PAYMENT:
            price_in_cents = apartment_data["right_of_occupancy_payment"]
        else:
            assert_never(ps)

        if self.is_numbered_payment():
            price_rounding = PriceRounding.EUROS
        else:
            price_rounding = PriceRounding.CENTS
        price = get_euros_from_cents(price_in_cents)
        percentage_multiplier = self.value / 100
        return get_rounded_price(price * percentage_multiplier, price_rounding)


class PaymentBatch(TimestampedModel):
    filename = models.CharField(
        verbose_name=_("Payment batch"), max_length=255, unique=True
    )

    class Meta:
        verbose_name = _("payment batch")
        verbose_name_plural = _("payment batches")
        ordering = ("id",)

    def __str__(self):
        return self.filename


class Payment(TimestampedModel):
    batch = models.ForeignKey(
        PaymentBatch,
        verbose_name=_("batch"),
        related_name="payments",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    apartment_installment = models.ForeignKey(
        ApartmentInstallment,
        verbose_name=_("apartment installment"),
        related_name="payments",
        on_delete=models.PROTECT,
    )
    amount = models.DecimalField(
        verbose_name=_("amount"), max_digits=16, decimal_places=2
    )
    payment_date = models.DateField(verbose_name=_("payment date"))

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ("id",)
