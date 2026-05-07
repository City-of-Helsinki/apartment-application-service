import statistics
import time
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from apartment.tests.factories import add_to_store, ApartmentDocumentFactory


def _median_elapsed_seconds(callable_, runs: int = 7) -> float:
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        callable_()
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


@pytest.mark.django_db
def test_project_list_load_time_with_and_without_sale_state_counts(
    settings, sales_ui_salesperson_api_client, elasticsearch, monkeypatch
):
    """
    Measure request wall time with and without sale state counts.

    This is a synthetic performance test:
    - We add a small deterministic delay to `get_apartment_uuids` to emulate
      the real Drupal search API HTTP roundtrip cost.
    - We then measure the `project-list` endpoint with the real code path vs
      a patched-out `get_project_apartment_sale_state_counts`.

    The assertion focuses on *relative* difference to stay stable in CI.
    """
    cache.clear()
    settings.DRUPAL_SEARCH_API_GET_CACHE_SECONDS = 0

    apartments = []
    try:
        for i in range(10):
            apartments.append(
                ApartmentDocumentFactory(
                    project_housing_company=f"Perf {i:02d}",
                    project_apartment_count=1,
                )
            )
        add_to_store(apartments)

        url = reverse("apartment:project-list")

        from apartment.elastic import queries

        original_get_apartment_uuids = queries.get_apartment_uuids

        def slow_get_apartment_uuids(project_uuid):
            time.sleep(0.03)
            return original_get_apartment_uuids(project_uuid)

        monkeypatch.setattr(queries, "get_apartment_uuids", slow_get_apartment_uuids)

        def real_call():
            response = sales_ui_salesperson_api_client.get(
                url, data={"page": 1, "page_size": 10}, format="json"
            )
            assert response.status_code == 200

        with_counts = _median_elapsed_seconds(real_call)

        with patch(
            "apartment.api.views.get_project_apartment_sale_state_counts",
            return_value={},
        ):

            def patched_call():
                response = sales_ui_salesperson_api_client.get(
                    url, data={"page": 1, "page_size": 10}, format="json"
                )
                assert response.status_code == 200

            without_counts = _median_elapsed_seconds(patched_call)

        # Expect the "with counts" path to be noticeably slower due to the
        # synthetic per-project delay (executed concurrently, so bounded by ~0.03s
        # plus overhead). We require a conservative margin for CI stability.
        assert with_counts > without_counts + 0.015
    finally:
        for apartment in apartments:
            apartment.delete(refresh=True)
