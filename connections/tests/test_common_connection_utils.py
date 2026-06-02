from decimal import Decimal

from connections.tests.factories import ApartmentMinimalFactory
from connections.utils import (
    build_project_floor_max_by_uuid,
    convert_price_from_cents_to_eur,
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
