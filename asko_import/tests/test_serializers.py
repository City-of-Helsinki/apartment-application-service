"""
Test cases for the validators of the AsKo import serializers.
"""

import pytest
from rest_framework.validators import UniqueTogetherValidator

from asko_import.serializers import (
    ApartmentInstallmentSerializer,
    ApartmentReservationSerializer,
    ApplicationApartmentSerializer,
    CustomerSerializer,
    LotteryEventResultSerializer,
    ProjectInstallmentTemplateSerializer,
)


def _unique_together_field_sets(serializer_class):
    """
    Return the field tuples of the serializer's UniqueTogetherValidators.

            Parameters:
                    serializer_class (type): Serializer class to inspect

            Returns:
                    field_sets (set): Set of field name tuples
    """
    return {
        tuple(validator.fields)
        for validator in serializer_class().validators
        if isinstance(validator, UniqueTogetherValidator)
    }


@pytest.mark.parametrize(
    "serializer_class",
    [
        CustomerSerializer,
        ProjectInstallmentTemplateSerializer,
        ApartmentInstallmentSerializer,
    ],
)
def test_serializer_has_no_constraint_derived_validators(serializer_class):
    """
    - No UniqueTogetherValidator is derived from Meta.constraints.
    - The validator set matches the one used before the DRF 3.16 upgrade.
    """
    assert serializer_class().validators == []


def test_apartment_reservation_serializer_keeps_unique_together_validator():
    """
    - The validator for Meta.unique_together (apartment_uuid,
      application_apartment) is kept.
    - No validator is derived from the deferrable (apartment_uuid,
      list_position) constraint.
    """
    field_sets = _unique_together_field_sets(ApartmentReservationSerializer)

    assert field_sets == {("apartment_uuid", "application_apartment")}
    assert ("apartment_uuid", "list_position") not in field_sets
    assert len(ApartmentReservationSerializer().validators) == 1


@pytest.mark.parametrize(
    "serializer_class,expected_fields",
    [
        (ApplicationApartmentSerializer, ("application", "priority_number")),
        (LotteryEventResultSerializer, ("event", "application_apartment")),
    ],
)
def test_unchanged_serializers_keep_unique_together_validator(
    serializer_class, expected_fields
):
    """
    - Serializers not affected by the upgrade keep their single
      Meta.unique_together derived validator.
    """
    assert _unique_together_field_sets(serializer_class) == {expected_fields}
