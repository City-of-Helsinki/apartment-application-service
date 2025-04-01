from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from enumfields import Enum


class InstallmentType(Enum):
    PAYMENT_1 = "PAYMENT_1"  # Erä 1.
    PAYMENT_2 = "PAYMENT_2"  # Erä 2.
    PAYMENT_3 = "PAYMENT_3"  # Erä 3.
    PAYMENT_4 = "PAYMENT_4"  # Erä 4.
    PAYMENT_5 = "PAYMENT_5"  # Erä 5.
    PAYMENT_6 = "PAYMENT_6"  # Erä 6.
    PAYMENT_7 = "PAYMENT_7"  # Erä 7.
    REFUND = "REFUND" # Hyvitys 1
    REFUND_2 = "REFUND_2"  # Hyvitys 2
    REFUND_3 = "REFUND_3"  # Hyvitys 3
    DOWN_PAYMENT = "DOWN_PAYMENT"  # Käsiraha
    LATE_PAYMENT_INTEREST = "LATE_PAYMENT_INTEREST"  # Viivästyskorko
    RIGHT_OF_OCCUPANCY_PAYMENT_1 = "RIGHT_OF_OCCUPANCY_PAYMENT_1"  # AO-maksu1
    RIGHT_OF_OCCUPANCY_PAYMENT_2 = "RIGHT_OF_OCCUPANCY_PAYMENT_2"  # AO-maksu2
    RIGHT_OF_OCCUPANCY_PAYMENT_3 = "RIGHT_OF_OCCUPANCY_PAYMENT_3"  # AO-maksu3
    FOR_INVOICING = "FOR_INVOICING"  # Laskutettava
    DEPOSIT = "DEPOSIT"  # Vakuusmaksu
    RESERVATION_FEE = "RESERVATION_FEE"  # Varausmaksu

    class Labels:
        PAYMENT_1 = _("1st payment")
        PAYMENT_2 = _("2nd payment")
        PAYMENT_3 = _("3rd payment")
        PAYMENT_4 = _("4th payment")
        PAYMENT_5 = _("5th payment")
        PAYMENT_6 = _("6th payment")
        PAYMENT_7 = _("7th payment")
        REFUND = _("refund 1")
        REFUND_1 = _("refund 1")
        REFUND_2 = _("refund 2")
        REFUND_3 = _("refund 3")
        DOWN_PAYMENT = _("down payment")
        LATE_PAYMENT_INTEREST = _("late payment interest")
        RIGHT_OF_OCCUPANCY_PAYMENT_1 = _("right of occupancy payment 1")
        RIGHT_OF_OCCUPANCY_PAYMENT_2 = _("right of occupancy payment 2")
        RIGHT_OF_OCCUPANCY_PAYMENT_3 = _("right of occupancy payment 3")
        FOR_INVOICING = _("for invoicing")
        DEPOSIT = _("deposit")
        RESERVATION_FEE = _("reservation fee")


class InstallmentUnit(Enum):
    EURO = "EURO"
    PERCENT = "PERCENT"

    class Labels:
        EURO = _("euro")
        PERCENT = _("percent")


class InstallmentPercentageSpecifier(Enum):
    SALES_PRICE = "SALES_PRICE"
    DEBT_FREE_SALES_PRICE = "DEBT_FREE_SALES_PRICE"
    SALES_PRICE_FLEXIBLE = "SALES_PRICE_FLEXIBLE"
    RIGHT_OF_OCCUPANCY_PAYMENT = "RIGHT_OF_OCCUPANCY_PAYMENT"

    class Labels:
        SALES_PRICE = _("sales price")
        DEBT_FREE_SALES_PRICE = _("debt free sales price")
        SALES_PRICE_FLEXIBLE = _("sales price flexible")
        RIGHT_OF_OCCUPANCY_PAYMENT = _("right of occupancy payment")


class PaymentStatus(Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    OVERPAID = "OVERPAID"
    UNDERPAID = "UNDERPAID"

    class Labels:
        PAID = _("paid")
        UNPAID = _("unpaid")
        OVERPAID = _("overpaid")
        UNDERPAID = _("underpaid")


class PriceRounding(Enum):
    CENTS = Decimal(".01")
    EUROS = Decimal("1")
