import pytest
from datetime import date
from decimal import Decimal
from pytest import mark

from cost_index.models import CostIndex
from cost_index.utils import calculate_end_value


@mark.django_db
def test_cost_index_utils_correct():
    cost_index_data = [
        {"value": Decimal("100.00"), "valid_from": date(2022, 11, 23)},
        {"value": Decimal("50.00"), "valid_from": date(2022, 11, 24)},
        {"value": Decimal("200.00"), "valid_from": date(2022, 11, 25)},
    ]
    cost_index_objs = [CostIndex(**data) for data in cost_index_data]
    CostIndex.objects.bulk_create(cost_index_objs)

    # Test the very basics
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 23), date(2022, 11, 23)
    ) == Decimal("100.00")
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 23), date(2022, 11, 24)
    ) == Decimal("50.00")
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 23), date(2022, 11, 25)
    ) == Decimal("200.00")
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 24), date(2022, 11, 25)
    ) == Decimal("400.00")

    # Test rounding behaviour
    assert calculate_end_value(
        Decimal("100.01"), date(2022, 11, 23), date(2022, 11, 24)
    ) == Decimal("50.00")

    with pytest.raises(ValueError):
        calculate_end_value(Decimal("100.00"), date(1988, 11, 22), date(2022, 11, 23))

    with pytest.raises(ValueError):
        calculate_end_value(Decimal("100.00"), date(1988, 11, 23), date(2022, 11, 22))
