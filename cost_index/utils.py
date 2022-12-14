import math
from datetime import date
from decimal import Decimal

from cost_index.models import CostIndex


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
