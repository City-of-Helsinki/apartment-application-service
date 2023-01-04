import math
from datetime import date
from decimal import Decimal

from cost_index.models import ApartmentRevaluation, CostIndex
from invoicing.enums import InstallmentType
from invoicing.models import ApartmentInstallment


def calculate_end_value(start_value: Decimal, start_date: date, end_date: date):
    start_index = determine_date_index(start_date)
    if start_index is None:
        raise ValueError("Start date is before the first CostIndex definition")

    end_index = determine_date_index(end_date)
    if end_index is None:
        raise ValueError("End date is before the first CostIndex definition")

    return adjust_value(start_value, start_index, end_index)


def determine_date_index(dt: date):
    index = CostIndex.objects.filter(valid_from__lte=dt).order_by("-valid_from").first()
    if index:
        return index.value
    return None


def adjust_value(value: Decimal, start_index: Decimal, end_index: Decimal):
    adjusted_value = value / start_index * end_index

    # Round to floor 2 decimals
    return Decimal(math.floor(adjusted_value * 100)) / 100


def current_right_of_occupancy_payment(
    apartment_uuid, original_right_of_occupancy_payment, not_after: date = None
):
    """
    Return current right of occupancy payment in cents
    """
    revaluation_qs = ApartmentRevaluation.objects.filter(
        apartment_reservation__apartment_uuid=apartment_uuid
    ).order_by("-end_date")

    if not_after:
        revaluation_qs = revaluation_qs.filter(end_date__lte=not_after)

    revaluation = revaluation_qs.first()
    if revaluation:
        return int(
            (
                revaluation.end_right_of_occupancy_payment
                + total_alteration_work(apartment_uuid)
            )
            * 100
        )
    return original_right_of_occupancy_payment


def reservation_right_of_occupancy_payment(
    reservation_id,
    apartment_uuid,
    original_right_of_occupancy_payment,
):
    """
    Three ways to calculate

    1) From matching revaluation (start_right_of_occupancy_payment)
    2) From previous revaluation
    3) From original price

    """
    try:
        reservation_revaluation = ApartmentRevaluation.objects.get(
            apartment_reservation_id=reservation_id
        )
        return int(reservation_revaluation.start_right_of_occupancy_payment * 100)

    except ApartmentRevaluation.DoesNotExist:
        pass

    try:
        reservation_payment1 = ApartmentInstallment.objects.get(
            apartment_reservation_id=reservation_id,
            type=InstallmentType.PAYMENT_1,
        )
        return current_right_of_occupancy_payment(
            apartment_uuid,
            original_right_of_occupancy_payment,
            not_after=reservation_payment1.due_date,
        )
    except ApartmentInstallment.DoesNotExist:
        return current_right_of_occupancy_payment(
            apartment_uuid, original_right_of_occupancy_payment
        )


def total_alteration_work(apartment_uuid) -> Decimal:
    return sum(
        ApartmentRevaluation.objects.filter(
            apartment_reservation__apartment_uuid=apartment_uuid
        ).values_list("alteration_work", flat=True)
    )
