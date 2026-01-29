from apartment.elastic import queries
from apartment.elastic.documents import ApartmentDocument
from apartment.tests.factories import add_to_store, ApartmentDocumentFactory
from apartment.tests.utils import TestDrupalSearchClient


class TestQueries:
    def test_to_results(self):
        """Tests apartment.elastic.queries._to_results with source dicts."""
        add_to_store(ApartmentDocumentFactory.create_batch(2))
        client = TestDrupalSearchClient()
        hits = client.get("apartments", params={"limit": 2, "offset": 0})["hits"][
            "hits"
        ]
        sources = [h.get("_source", {}) for h in hits]
        results = queries._to_results(sources, include_project_fields=True)

        assert all(
            isinstance(result, ApartmentDocument) for result in results
        ), "Should return ApartmentDocument objects"
