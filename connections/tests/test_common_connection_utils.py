from decimal import Decimal

from connections.tests.factories import ApartmentMinimalFactory
from connections.utils import (
    build_project_floor_max_by_uuid,
    build_staircase_floor_max_by_uuid,
    convert_price_from_cents_to_eur,
    join_multi_value_field,
    parse_staircase_letter,
    resolve_floor_max,
)


class TestCommonConnectionUtils:
    def test_convert_price_from_cents_to_eur(self):
        assert convert_price_from_cents_to_eur(10000) == Decimal("100.0")
        assert convert_price_from_cents_to_eur(12345.67) == Decimal("123.46")


class TestFloorMaxResolution:
    def test_resolve_floor_max_returns_none_when_no_values(self):
        """
        - Returns None when floor and floor_max are both missing.
        """
        apartment = ApartmentMinimalFactory(floor=None, floor_max=None)
        assert resolve_floor_max(apartment) is None

    def test_resolve_floor_max_uses_floor_when_floor_max_too_low(self):
        """
        - Uses apartment floor when it exceeds floor_max.
        """
        apartment = ApartmentMinimalFactory(floor=5, floor_max=1)
        assert resolve_floor_max(apartment) == 5

    def test_resolve_floor_max_uses_project_max_when_higher(self):
        """
        - Uses project-level maximum when it exceeds apartment floor_max.
        """
        apartment = ApartmentMinimalFactory(floor=3, floor_max=1)
        assert resolve_floor_max(apartment, project_floor_max=8) == 8

    def test_build_project_floor_max_by_uuid(self):
        """
        - Computes the highest floor or floor_max per project_uuid.
        """
        project_uuid = "same-project-uuid"
        apt1 = ApartmentMinimalFactory(project_uuid=project_uuid, floor=2, floor_max=1)
        apt2 = ApartmentMinimalFactory(project_uuid=project_uuid, floor=7, floor_max=6)
        apt3 = ApartmentMinimalFactory(project_uuid="other", floor=1, floor_max=3)
        lookup = build_project_floor_max_by_uuid([apt1, apt2, apt3])
        assert lookup[project_uuid] == 7
        assert lookup["other"] == 3

    def test_resolve_floor_max_prefers_staircase_max_over_project_max(self):
        """
        - Uses staircase-level max instead of project max when both are given.
        """
        apartment = ApartmentMinimalFactory(
            apartment_number="C62",
            floor=4,
            floor_max=1,
        )
        assert (
            resolve_floor_max(apartment, project_floor_max=8, staircase_floor_max=4)
            == 4
        )

    def test_parse_staircase_letter(self):
        """
        - Extracts leading letter from apartment_number.
        - Returns None when apartment_number has no leading letter.
        """
        assert parse_staircase_letter("A12") == "A"
        assert parse_staircase_letter("C62") == "C"
        assert parse_staircase_letter("E02") == "E"
        assert parse_staircase_letter("C 12") == "C"
        assert parse_staircase_letter(None) is None
        assert parse_staircase_letter("12") is None

    def test_build_staircase_floor_max_by_uuid(self):
        """
        - Computes the highest floor or floor_max per project and staircase.
        """
        project_uuid = "same-project-uuid"
        apt_a1 = ApartmentMinimalFactory(
            project_uuid=project_uuid,
            apartment_number="A12",
            floor=2,
            floor_max=1,
        )
        apt_a2 = ApartmentMinimalFactory(
            project_uuid=project_uuid,
            apartment_number="A08",
            floor=8,
            floor_max=1,
        )
        apt_c1 = ApartmentMinimalFactory(
            project_uuid=project_uuid,
            apartment_number="C04",
            floor=4,
            floor_max=1,
        )
        apt_other_project = ApartmentMinimalFactory(
            project_uuid="other",
            apartment_number="A03",
            floor=3,
            floor_max=2,
        )
        lookup = build_staircase_floor_max_by_uuid(
            [apt_a1, apt_a2, apt_c1, apt_other_project]
        )
        assert lookup[f"{project_uuid}:A"] == 8
        assert lookup[f"{project_uuid}:C"] == 4
        assert lookup["other:A"] == 3


class TestJoinMultiValueField:
    def test_join_multi_value_field_with_list(self):
        """
        - Joins list items into a comma-separated string.
        """
        assert join_multi_value_field(["Betoni"]) == "Betoni"
        assert join_multi_value_field(["Betoni", "Tiili"]) == "Betoni, Tiili"

    def test_join_multi_value_field_with_string(self):
        """
        - Treats a plain string as a single value, not individual characters.
        """
        assert join_multi_value_field("Betoni") == "Betoni"

    def test_join_multi_value_field_with_empty_values(self):
        """
        - Returns None for missing or empty values.
        """
        assert join_multi_value_field(None) is None
        assert join_multi_value_field([]) is None
        assert join_multi_value_field("") is None
