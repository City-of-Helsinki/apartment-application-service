import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from freezegun import freeze_time
from pytest import mark

from application_form.enums import ApartmentReservationState
from application_form.tests.factories import ApartmentReservationFactory
from cost_index.models import CostIndex
from cost_index.tests.factories import ApartmentRevaluationFactory
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
