from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from freezegun import freeze_time
from pytest import mark

from application_form.enums import ApartmentReservationState
from application_form.tests.factories import ApartmentReservationFactory
from cost_index.models import CostIndex
from cost_index.tests.factories import ApartmentRevaluationFactory
from cost_index.utils import adjust_value, calculate_end_value, determine_date_index


@mark.django_db
def test_cost_index_no_price_decrease():
    """
    Assert that the price of an apartment doesn't go down if the price index has
    gone down from original purchase date.

    e.g. Cost index at 7.3.2024 is 100.0 and on 7.3.2025 its 90
    """
    original_value = 10_000
    assert (
        adjust_value(
            original_value,
            start_index=Decimal("100.00"),
            end_index=Decimal("90.00"),
        )
        >= original_value
    )
    assert (
        adjust_value(
            original_value,
            start_index=Decimal("100.00"),
            end_index=Decimal("110.00"),
        )
        == 11_000
    )

    pass


@mark.django_db
def test_cost_index_utils_correct():
    cost_index_data = [
        {"value": Decimal("99.998"), "valid_from": date(2022, 11, 23)},
        {"value": Decimal("50.00"), "valid_from": date(2022, 11, 24)},
        {"value": Decimal("200.00"), "valid_from": date(2022, 11, 25)},
        {"value": Decimal("200.998"), "valid_from": date(2022, 11, 26)},
    ]
    cost_index_objs = [CostIndex(**data) for data in cost_index_data]
    CostIndex.objects.bulk_create(cost_index_objs)

    # Test the very basics
    assert calculate_end_value(
        Decimal("99.989"), date(2022, 11, 23), date(2022, 11, 23)
    ) == Decimal("99.99")
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 23), date(2022, 11, 24)
    ) == Decimal(
        "100.00"
    )  # value shouldn't be adjusted downwards
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 23), date(2022, 11, 25)
    ) == Decimal("200.00")
    assert calculate_end_value(
        Decimal("100.00"), date(2022, 11, 24), date(2022, 11, 25)
    ) == Decimal("400.00")

    # Test rounding behaviour
    assert calculate_end_value(
        Decimal("100.01"), date(2022, 11, 23), date(2022, 11, 26)
    ) == Decimal("201.02")

    with pytest.raises(ValueError):
        calculate_end_value(Decimal("100.00"), date(1988, 11, 22), date(2022, 11, 23))

    with pytest.raises(ValueError):
        calculate_end_value(Decimal("100.00"), date(1988, 11, 23), date(2022, 11, 22))


@pytest.mark.django_db
def test_apartment_revaluation_effect_on_apartment_document(
    drupal_server_api_client, elastic_haso_project_with_5_apartments
):
    _, haso_apartments = elastic_haso_project_with_5_apartments

    haso_0 = haso_apartments[0]
    haso_0_reservation_0 = ApartmentReservationFactory(
        apartment_uuid=haso_0.uuid,
        state=ApartmentReservationState.CANCELED,
        list_position=1,
    )
    assert (
        haso_0.right_of_occupancy_payment == haso_0.current_right_of_occupancy_payment
    )

    now = timezone.now()
    with freeze_time(now - timedelta(hours=2000)):
        ApartmentRevaluationFactory(
            apartment_reservation=haso_0_reservation_0,
        )

    assert (
        haso_0.right_of_occupancy_payment != haso_0.current_right_of_occupancy_payment
    )
