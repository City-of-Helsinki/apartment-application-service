from typing import Any, Dict, List, Optional

from apartment.elastic import queries
from apartment.elastic.queries import _fetch_all

# Drupal GET /apartments and /projects/{uuid}/apartments cap size at 250.
DRUPAL_APARTMENTS_PAGE_CAP = 250


class _CappedSearchClient:
    """Drupal-like client that caps each page below the requested limit."""

    def __init__(
        self,
        sources: List[Dict[str, Any]],
        page_cap: int = DRUPAL_APARTMENTS_PAGE_CAP,
        include_total: bool = True,
    ):
        """
        Parameters:
            sources: Full hit list the client pages over.
            page_cap: Max hits per response (Drupal apartments max is 250).
            include_total: When False, omit hits.total from the payload.
        """
        self.sources = sources
        self.page_cap = page_cap
        self.include_total = include_total
        self.calls: List[Dict[str, Any]] = []

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Return one ES-style page, capped at page_cap regardless of requested
        limit.
        """
        params = dict(params or {})
        self.calls.append({"path": path, "params": params, "timeout": timeout})
        offset = int(params.get("offset", 0))
        requested = int(params.get("limit", self.page_cap))
        limit = min(requested, self.page_cap)
        page = self.sources[offset : offset + limit]
        hits = [{"_source": source} for source in page]
        payload: Dict[str, Any] = {"hits": {"hits": hits}}
        if self.include_total:
            payload["hits"]["total"] = {"value": len(self.sources)}
        return payload


def _source(index: int) -> Dict[str, str]:
    """Return a minimal apartment _source keyed by a stable fake UUID."""
    return {"uuid": f"{index:08d}-0000-0000-0000-000000000000"}


def _call_offsets(client: _CappedSearchClient) -> List[int]:
    """Return the offset query param from each client.get call."""
    return [int(call["params"].get("offset", 0)) for call in client.calls]


def _first_page_size(client: _CappedSearchClient, total: int) -> int:
    """Return how many hits the fake Drupal cap would serve on the first page."""
    requested = int(client.calls[0]["params"].get("limit", DRUPAL_APARTMENTS_PAGE_CAP))
    return min(requested, DRUPAL_APARTMENTS_PAGE_CAP, total)


def _install_client(monkeypatch, client: _CappedSearchClient) -> None:
    """
    Point _fetch_all at the capped fake client.

    apartment/tests/conftest.py autouse-patches queries._fetch_all; restore
    the real function so these tests exercise production pagination.
    """
    monkeypatch.setattr(queries, "_fetch_all", _fetch_all)
    monkeypatch.setattr(queries, "_get_client", lambda: client)


def test_fetch_all_paginates_when_server_caps_page_below_requested_limit(
    monkeypatch,
):
    """
    Drupal caps apartment pages at 250 while the client may request 1000.

    - 600 hits must all be returned.
    - Each request offset must equal the number of hits already collected.
    - A first page shorter than the requested limit is not the last page.
    """
    client = _CappedSearchClient([_source(i) for i in range(600)])
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={})

    assert [source["uuid"] for source in sources] == [
        _source(i)["uuid"] for i in range(600)
    ]
    offsets = _call_offsets(client)
    assert offsets[0] == 0
    collected = 0
    for offset, call in zip(offsets, client.calls):
        assert offset == collected
        requested = int(call["params"].get("limit", DRUPAL_APARTMENTS_PAGE_CAP))
        collected += min(requested, DRUPAL_APARTMENTS_PAGE_CAP, 600 - collected)
    assert collected == 600
    assert all(offset < 600 for offset in offsets)


def test_fetch_all_includes_short_final_page(monkeypatch):
    """
    The last page may be smaller than the Drupal cap and must still be kept.

    - 300 hits with a 250 cap -> 250 from the first page and 50 from the last.
    - Stopping after the first short-vs-requested page would drop 50 hits.
    """
    client = _CappedSearchClient([_source(i) for i in range(300)])
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={})

    assert len(sources) == 300
    assert sources[0]["uuid"] == _source(0)["uuid"]
    assert sources[249]["uuid"] == _source(249)["uuid"]
    assert sources[250]["uuid"] == _source(250)["uuid"]
    assert sources[-1]["uuid"] == _source(299)["uuid"]
    offsets = _call_offsets(client)
    assert len(offsets) >= 2
    assert offsets[1] == _first_page_size(client, 300)


def test_fetch_all_does_not_skip_hits_after_capped_page(monkeypatch):
    """
    Offset must advance by returned hits, not by the requested 1000.

    - 400 hits, cap 250: the second request must use offset 250.
    - Offset 1000 would skip the remaining 150 hits (and look like completion).
    """
    client = _CappedSearchClient([_source(i) for i in range(400)])
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={})

    assert len(sources) == 400
    offsets = _call_offsets(client)
    assert 1000 not in offsets
    assert len(offsets) >= 2
    assert offsets[1] == _first_page_size(client, 400)


def test_fetch_all_returns_empty_list_when_index_is_empty(monkeypatch):
    """
    An empty index must not raise or invent hits.

    - total 0 and no hits -> [].
    - A single request is enough.
    """
    client = _CappedSearchClient([])
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={})

    assert sources == []
    assert len(client.calls) == 1
    assert _call_offsets(client) == [0]


def test_fetch_all_stops_on_empty_page_when_total_is_missing(monkeypatch):
    """
    Missing hits.total must not loop forever.

    - First page returns capped hits without a total.
    - Next page is empty -> stop with the first page's hits.
    """
    client = _CappedSearchClient(
        [_source(i) for i in range(250)],
        include_total=False,
    )
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={})

    assert len(sources) == 250
    assert len(client.calls) >= 1
    assert len(client.calls) <= 2
    if len(client.calls) == 2:
        assert int(client.calls[1]["params"].get("offset", 0)) == 250


def test_fetch_all_paginates_until_empty_when_total_is_missing(monkeypatch):
    """
    Without hits.total, keep paging until Drupal returns no hits.

    - 600 hits, cap 250, no total -> all 600 returned.
    - Must not stop after the first short-vs-requested page.
    """
    client = _CappedSearchClient(
        [_source(i) for i in range(600)],
        include_total=False,
    )
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={})

    assert [source["uuid"] for source in sources] == [
        _source(i)["uuid"] for i in range(600)
    ]
    assert _call_offsets(client)[0] == 0
    assert 1000 not in _call_offsets(client)


def test_fetch_all_forwards_filters_on_every_page(monkeypatch):
    """
    Caller filters must be sent on each paginated request.

    - publish_on_etuovi is present on every GET.
    - Path stays apartments.
    """
    client = _CappedSearchClient([_source(i) for i in range(300)])
    _install_client(monkeypatch, client)

    _fetch_all("apartments", params={"publish_on_etuovi": True})

    assert len(client.calls) >= 2
    for call in client.calls:
        assert call["path"] == "apartments"
        assert call["params"]["publish_on_etuovi"] is True


def test_fetch_all_explicit_limit_does_not_paginate(monkeypatch):
    """
    Callers that set limit (e.g. get_apartments(limit=1)) get one page.

    - total may be larger than limit.
    - Only one HTTP GET is made.
    """
    client = _CappedSearchClient([_source(i) for i in range(400)])
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={"limit": 1})

    assert len(sources) == 1
    assert sources[0]["uuid"] == _source(0)["uuid"]
    assert len(client.calls) == 1


def test_fetch_all_explicit_limit_does_not_return_hits_beyond_limit(monkeypatch):
    """
    Explicit limit must not be treated as a request to scan the full index.

    - limit=1 against 400 hits still returns a single document.
    """
    client = _CappedSearchClient([_source(i) for i in range(400)])
    _install_client(monkeypatch, client)

    sources = _fetch_all("apartments", params={"limit": 1})

    assert [source["uuid"] for source in sources] != [
        _source(i)["uuid"] for i in range(400)
    ]
    assert len(sources) < 400
