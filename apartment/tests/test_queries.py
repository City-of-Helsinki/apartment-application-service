import pytest

from apartment.elastic.queries import get_project_apartment_sale_state_counts
from apartment.tests.factories import add_to_store, ApartmentDocumentFactory
from application_form.enums import ApartmentReservationState
from application_form.tests.factories import ApartmentReservationFactory


@pytest.mark.django_db
def test_sale_state_counts_empty_input_returns_empty_dict():
    """
    Verify that passing an empty iterable short-circuits to an empty mapping.

    - No project UUIDs -> no API calls and no keys in the result.
    """
    assert get_project_apartment_sale_state_counts([]) == {}


@pytest.mark.django_db
def test_get_apartment_uuids_is_cached(monkeypatch):
    """
    Verify that apartment UUID lookup is cached per project.

    - First call performs a Drupal search API fetch.
    - Second call for same project UUID is served from cache.
    """
    from django.core.cache import cache

    from apartment.elastic import queries

    cache.clear()

    project_uuid = "22222222-2222-2222-2222-222222222222"
    fetch_calls = {"count": 0}

    def fake_fetch_all(path: str, params: dict):
        fetch_calls["count"] += 1
        assert path == f"projects/{project_uuid}/apartments"
        assert params == {}
        return [
            {"uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
            {"uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
            {"uuid": None},
        ]

    monkeypatch.setattr(queries, "_fetch_all", fake_fetch_all)

    assert queries.get_apartment_uuids(project_uuid) == [
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    ]
    assert queries.get_apartment_uuids(project_uuid) == [
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    ]
    assert fetch_calls["count"] == 1


@pytest.mark.django_db
def test_get_apartment_uuids_for_projects_empty_returns_empty_list():
    """
    Verify that an empty project list yields no apartment UUIDs.

    - No HTTP or cache lookups for an empty input.
    """
    from apartment.elastic import queries

    assert queries.get_apartment_uuids_for_projects([]) == []


@pytest.mark.django_db
def test_get_apartment_uuids_for_projects_merges_parallel_lookups(monkeypatch):
    """
    Verify multi-project resolution aggregates UUIDs from each project.

    - Duplicate project UUIDs in the input are de-duplicated before fetch.
    - ``get_apartment_uuids`` is invoked once per distinct project.
    """
    from apartment.elastic import queries

    p1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    p2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    calls = []

    def fake_get_apartment_uuids(project_uuid):
        calls.append(str(project_uuid))
        if str(project_uuid) == p1:
            return ["u1", "u2"]
        return ["u3"]

    monkeypatch.setattr(queries, "get_apartment_uuids", fake_get_apartment_uuids)

    result = queries.get_apartment_uuids_for_projects([p1, p2, p1])

    assert set(calls) == {p1, p2}
    assert len(calls) == 2
    assert set(result) == {"u1", "u2", "u3"}


@pytest.mark.django_db
def test_sale_state_counts_project_without_apartments_returns_zeros(
    elasticsearch,
):
    """
    Verify that projects with no indexed apartments return all zero counts.

    - Requested project UUID must always appear in the result mapping.
    - All three count buckets must be 0.
    """
    missing_project_uuid = "11111111-1111-1111-1111-111111111111"

    result = get_project_apartment_sale_state_counts([missing_project_uuid])

    assert result == {
        missing_project_uuid: {
            "sold_apartment_count": 0,
            "reserved_apartment_count": 0,
            "free_apartment_count": 0,
        }
    }


@pytest.mark.django_db
def test_sale_state_counts_apartments_without_reservations_are_free(
    elasticsearch,
):
    """
    Verify apartments with no winning reservation count as 'free'.

    - 3 apartments, 0 reservations -> all 3 counted as free.
    """
    first = ApartmentDocumentFactory()
    apartments = [
        first,
        ApartmentDocumentFactory(project_uuid=first.project_uuid),
        ApartmentDocumentFactory(project_uuid=first.project_uuid),
    ]
    add_to_store(apartments)

    result = get_project_apartment_sale_state_counts([str(first.project_uuid)])

    assert result == {
        str(first.project_uuid): {
            "sold_apartment_count": 0,
            "reserved_apartment_count": 0,
            "free_apartment_count": 3,
        }
    }


@pytest.mark.django_db
def test_sale_state_counts_categorizes_by_winning_reservation_state(
    elasticsearch,
):
    """
    Verify that the winning reservation (list_position=1) drives categorization.

    - SOLD state -> sold_apartment_count.
    - RESERVED state -> reserved_apartment_count.
    - SUBMITTED state -> free_apartment_count (treated as not-yet-reserved).
    - No reservation -> free_apartment_count.
    """
    first = ApartmentDocumentFactory()
    sold_apt = first
    reserved_apt = ApartmentDocumentFactory(project_uuid=first.project_uuid)
    submitted_apt = ApartmentDocumentFactory(project_uuid=first.project_uuid)
    no_reservation_apt = ApartmentDocumentFactory(project_uuid=first.project_uuid)
    add_to_store([sold_apt, reserved_apt, submitted_apt, no_reservation_apt])

    ApartmentReservationFactory(
        apartment_uuid=sold_apt.uuid,
        state=ApartmentReservationState.SOLD,
        list_position=1,
    )
    ApartmentReservationFactory(
        apartment_uuid=reserved_apt.uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
    )
    ApartmentReservationFactory(
        apartment_uuid=submitted_apt.uuid,
        state=ApartmentReservationState.SUBMITTED,
        list_position=1,
    )

    result = get_project_apartment_sale_state_counts([str(first.project_uuid)])

    assert result[str(first.project_uuid)] == {
        "sold_apartment_count": 1,
        "reserved_apartment_count": 1,
        "free_apartment_count": 2,
    }


@pytest.mark.django_db
def test_sale_state_counts_only_counts_list_position_one(
    elasticsearch,
):
    """
    Verify that only the winning (list_position=1) reservation is considered.

    - A later list_position=2 reservation must not influence the count.
    - With list_position=1 RESERVED and list_position=2 OFFERED the apartment
      is counted as reserved.
    """
    first = ApartmentDocumentFactory()
    add_to_store([first])

    ApartmentReservationFactory(
        apartment_uuid=first.uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
    )
    ApartmentReservationFactory(
        apartment_uuid=first.uuid,
        state=ApartmentReservationState.OFFERED,
        list_position=2,
    )

    result = get_project_apartment_sale_state_counts([str(first.project_uuid)])

    assert result[str(first.project_uuid)] == {
        "sold_apartment_count": 0,
        "reserved_apartment_count": 1,
        "free_apartment_count": 0,
    }


@pytest.mark.django_db
def test_sale_state_counts_excludes_canceled_reservations(
    elasticsearch,
):
    """
    Verify that canceled reservations are excluded via the .active() manager.

    - Canceled winning reservation is ignored.
    - The apartment falls back to 'free' when no other active winner exists.
    """
    first = ApartmentDocumentFactory()
    add_to_store([first])

    ApartmentReservationFactory(
        apartment_uuid=first.uuid,
        state=ApartmentReservationState.CANCELED,
        list_position=1,
    )

    result = get_project_apartment_sale_state_counts([str(first.project_uuid)])

    assert result[str(first.project_uuid)] == {
        "sold_apartment_count": 0,
        "reserved_apartment_count": 0,
        "free_apartment_count": 1,
    }


@pytest.mark.django_db
def test_sale_state_counts_keeps_projects_independent(
    elasticsearch,
):
    """
    Verify that multi-project input yields independent per-project counts.

    - Counts from one project must not leak into another.
    - Both requested project UUIDs must be present in the output.
    """
    project_a_apt = ApartmentDocumentFactory()
    project_b_apt = ApartmentDocumentFactory()
    add_to_store([project_a_apt, project_b_apt])

    ApartmentReservationFactory(
        apartment_uuid=project_a_apt.uuid,
        state=ApartmentReservationState.SOLD,
        list_position=1,
    )
    ApartmentReservationFactory(
        apartment_uuid=project_b_apt.uuid,
        state=ApartmentReservationState.RESERVED,
        list_position=1,
    )

    result = get_project_apartment_sale_state_counts(
        [str(project_a_apt.project_uuid), str(project_b_apt.project_uuid)]
    )

    assert result[str(project_a_apt.project_uuid)] == {
        "sold_apartment_count": 1,
        "reserved_apartment_count": 0,
        "free_apartment_count": 0,
    }
    assert result[str(project_b_apt.project_uuid)] == {
        "sold_apartment_count": 0,
        "reserved_apartment_count": 1,
        "free_apartment_count": 0,
    }


@pytest.mark.django_db
def test_sale_state_counts_fetches_projects_concurrently(elasticsearch, monkeypatch):
    """
    Verify that per-project apartment lookups are dispatched concurrently.

    - With 4 artificially-slow per-project fetches (~0.2s each) the total
      wall-clock time must be well below the sequential worst case.
    - This guards against regressing back to serial per-project HTTP calls,
      which is the historical performance bottleneck.
    """
    import time

    from apartment.elastic import queries

    projects = [ApartmentDocumentFactory() for _ in range(4)]
    add_to_store(projects)
    project_uuids = [str(apt.project_uuid) for apt in projects]

    original_get_apartment_uuids = queries.get_apartment_uuids

    def slow_get_apartment_uuids(project_uuid):
        time.sleep(0.2)
        return original_get_apartment_uuids(project_uuid)

    monkeypatch.setattr(queries, "get_apartment_uuids", slow_get_apartment_uuids)

    start = time.perf_counter()
    result = get_project_apartment_sale_state_counts(project_uuids)
    elapsed = time.perf_counter() - start

    # Sequential would take ~0.8s; concurrent should finish in well under 0.5s.
    assert elapsed < 0.5, f"Expected concurrent execution, took {elapsed:.3f}s"
    assert set(result.keys()) == set(project_uuids)


def test_get_projects_for_uuids_empty_returns_empty_list():
    """
    ``get_projects_for_uuids`` with no UUIDs must return an empty list.

    - No HTTP and no thread pool work for an empty input.
    """
    from apartment.elastic import queries

    assert queries.get_projects_for_uuids([]) == []


@pytest.mark.django_db
def test_get_projects_for_uuids_deduplicates_and_preserves_order(monkeypatch):
    """
    Duplicate UUIDs are fetched once; output order follows first occurrence.

    - ``get_project`` is invoked once per distinct project UUID.
    """
    from apartment.elastic import queries

    p1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    p2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    calls = []

    def fake_get_project(project_uuid):
        calls.append(str(project_uuid))
        return {"project_uuid": str(project_uuid)}

    monkeypatch.setattr(queries, "get_project", fake_get_project)

    result = queries.get_projects_for_uuids([p1, p2, p1])

    assert calls == [p1, p2]
    assert [p["project_uuid"] for p in result] == [p1, p2]


@pytest.mark.django_db
def test_get_projects_for_uuids_skips_missing_projects(monkeypatch):
    """
    Projects that no longer exist in Drupal search are omitted from the result.

    - ``ObjectDoesNotExist`` from ``get_project`` must not fail the whole batch.
    """
    from django.core.exceptions import ObjectDoesNotExist

    from apartment.elastic import queries

    existing = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    missing = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def fake_get_project(project_uuid):
        if str(project_uuid) == missing:
            raise ObjectDoesNotExist()
        return {"project_uuid": str(project_uuid)}

    monkeypatch.setattr(queries, "get_project", fake_get_project)

    result = queries.get_projects_for_uuids([existing, missing])

    assert [p["project_uuid"] for p in result] == [existing]


def test_get_apartments_for_uuids_empty_returns_empty_dict():
    """
    ``get_apartments_for_uuids`` with no UUIDs must return an empty dict.

    - No HTTP and no thread pool work for an empty input.
    """
    from apartment.elastic import queries

    assert queries.get_apartments_for_uuids([]) == {}


def test_get_apartments_for_uuids_deduplicates(elasticsearch):
    """
    Duplicate UUIDs in the input must yield a single Drupal GET per distinct id.

    - Two physical apartments plus a repeated first UUID -> two map entries.
    """
    from apartment.elastic import queries

    first = ApartmentDocumentFactory()
    second = ApartmentDocumentFactory()
    add_to_store([first, second])

    result = queries.get_apartments_for_uuids(
        [first.uuid, second.uuid, first.uuid], include_project_fields=True
    )

    assert set(result.keys()) == {str(first.uuid), str(second.uuid)}
    assert str(result[str(first.uuid)].uuid) == str(first.uuid)


def test_get_apartment_second_call_uses_cache(elasticsearch, monkeypatch):
    """
    Two ``get_apartment`` calls with the same arguments hit Drupal Search once.

    - The in-process cache must short-circuit the second HTTP GET.
    """
    from django.core.cache import cache

    from apartment.elastic import queries
    from apartment.tests.utils import TestDrupalSearchClient

    cache.clear()
    apartment = ApartmentDocumentFactory()
    add_to_store([apartment])

    paths = []

    original_get = TestDrupalSearchClient.get

    def counting_get(self, path, params=None, timeout=None):
        paths.append(path)
        return original_get(self, path, params, timeout)

    monkeypatch.setattr(TestDrupalSearchClient, "get", counting_get)

    queries.get_apartment(str(apartment.uuid), include_project_fields=True)
    queries.get_apartment(str(apartment.uuid), include_project_fields=True)

    apartment_paths = [p for p in paths if p.startswith("apartments/")]
    assert len(apartment_paths) == 1
