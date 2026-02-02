from apartment.tests.factories import ApartmentDocumentFactory, add_to_store
from apartment.tests.utils import TestDrupalSearchClient
import pytest
from apartment.elastic import queries
from apartment.elastic.documents import ApartmentDocument

class TestQueries:
    def test_to_results(self):
        """Tests apartment.elastic.queries._to_results function."""
        add_to_store(ApartmentDocumentFactory.create_batch(2))
        client = TestDrupalSearchClient()
        sources = client.get("apartments", params={"limit": 2, "offset": 0})["hits"]["hits"]
        results = queries._to_results(sources, include_project_fields=True)

        assert all(
            isinstance(result, ApartmentDocument) for result in results
        ), "Should return ApartmentDocument objects"

