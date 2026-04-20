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
