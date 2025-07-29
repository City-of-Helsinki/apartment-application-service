from unittest.mock import patch

import pytest
from django_etuovi.utils.testing import check_dataclass_typing

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from connections.etuovi import etuovi_mapper
from connections.oikotie import oikotie_mapper
from connections.utils import map_document


class TestMapperHandler:
    @pytest.mark.parametrize(
        "ownership_type", [OwnershipType.HASO, OwnershipType.HITAS]
    )
    def test_mapper_works_correctly(self, ownership_type):
        apartment = ApartmentDocumentFactory(
            project_ownership_type=ownership_type.value,
        )
        mapper_funcs = [
            etuovi_mapper.map_apartment_to_item,
            oikotie_mapper.map_apartment,
            oikotie_mapper.map_oikotie_housing_company,
        ]
        for mapper_func in mapper_funcs:
            check_dataclass_typing(map_document(apartment, mapper_func))
        pass

    @pytest.mark.parametrize(
        "ownership_type", [OwnershipType.HASO, OwnershipType.HITAS]
    )
    @patch("connections.utils._logger")
    def test_mapper_handles_error(self, patched_logger, ownership_type):
        apartment = ApartmentDocumentFactory(
            project_ownership_type=ownership_type.value,
        )

        # deliberately make ApartmentDocument faulty
        delattr(apartment, "project_building_type")
        delattr(apartment, "project_city")

        mapper_funcs = [
            etuovi_mapper.map_apartment_to_item,
            oikotie_mapper.map_apartment,
            oikotie_mapper.map_oikotie_housing_company,
        ]
        for mapper_func in mapper_funcs:
            item = map_document(apartment, mapper_func)
            assert item is None

        assert patched_logger.error.call_count == 3
        assert patched_logger.warning.call_count == 3
