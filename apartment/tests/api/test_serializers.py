import pytest

from apartment.api.serializers import ProjectDocumentListSerializer
from apartment.tests.factories import ApartmentDocumentFactory


@pytest.mark.django_db
def test_project_list_serializer_allows_empty_construction_year():
	project = ApartmentDocumentFactory(project_construction_year="")

	serializer = ProjectDocumentListSerializer(
		[project],
		many=True,
		context={"apartment_sale_state_counts": {}},
	)

	assert serializer.data[0]["construction_year"] is None


@pytest.mark.django_db
def test_project_list_serializer_allows_construction_year_range_string():
	project = ApartmentDocumentFactory(project_construction_year="2022-2025")

	serializer = ProjectDocumentListSerializer(
		[project],
		many=True,
		context={"apartment_sale_state_counts": {}},
	)

	assert serializer.data[0]["construction_year"] is None
