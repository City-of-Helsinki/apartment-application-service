import math
from datetime import date
from decimal import Decimal
from typing import Optional

from cost_index.models import CostIndex


def calculate_end_value(
    start_value: Decimal,
    start_date: date,
    end_date: date,
    add: Optional[Decimal] = None,
):
    start_index = (
        CostIndex.objects.filter(valid_from__lte=start_date)
        .order_by("-valid_from")
        .first()
    )
    if start_index is None:
        raise ValueError("Start date is before the first CostIndex definition")

    end_index = (
        CostIndex.objects.filter(valid_from__lte=end_date)
        .order_by("-valid_from")
        .first()
    )
    if end_index is None:
        raise ValueError("End date is before the first CostIndex definition")

    end_value = start_value / start_index.value * end_index.value
    if add:
        end_value += add

    return Decimal(math.floor(end_value * 100)) / 100
