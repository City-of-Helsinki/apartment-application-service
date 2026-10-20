import json

import pytest

from e2e.scenarios import registry
from e2e.scenarios.registry import ScenarioParamsError
from e2e.seeder.server import dispatch

FAKE_MANIFEST = {"scenario": "fake", "apartment_uuid": "e2e00001-0000"}


@pytest.fixture
def calls():
    """
    Return the list recording params passed to the fake scenarios.

            Returns:
                    calls (list): (scenario name, params) tuples
    """
    return []


@pytest.fixture
def fake_scenarios(monkeypatch, calls):
    """
    Replace the scenario registry with fake scenarios.

    Registered: "fake" (returns FAKE_MANIFEST), "bad_params" (raises
    ScenarioParamsError) and "boom" (raises RuntimeError).

            Parameters:
                    monkeypatch: pytest monkeypatch fixture
                    calls (list): Records (name, params) of every invocation

            Returns:
                    scenarios (dict): The installed registry
    """

    def fake(params):
        """Record the call and return the fake manifest."""
        calls.append(("fake", params))
        return dict(FAKE_MANIFEST)

    def bad_params(params):
        """Record the call and reject the params."""
        calls.append(("bad_params", params))
        raise ScenarioParamsError("variant must be one of on_time, late")

    def boom(params):
        """Record the call and fail unexpectedly."""
        calls.append(("boom", params))
        raise RuntimeError("database exploded")

    scenarios = {"fake": fake, "bad_params": bad_params, "boom": boom}
    monkeypatch.setattr(registry, "_SCENARIOS", scenarios)
    return scenarios


def _assert_error(response, status):
    """
    Assert a dispatch result is an error response with the given status.

            Parameters:
                    response (tuple): (status, body) returned by dispatch
                    status (int): Expected HTTP status
    """
    actual_status, body = response
    assert actual_status == status
    assert isinstance(body, dict)
    assert isinstance(body.get("error"), str)
    assert body["error"]
    json.dumps(body)


def test_health_lists_registered_scenarios(fake_scenarios):
    """
    - GET /health returns 200 with status ok and sorted scenario names
    """
    status, body = dispatch("GET", "/health", b"")

    assert status == 200
    assert body == {"status": "ok", "scenarios": ["bad_params", "boom", "fake"]}


def test_health_lists_haso_queue_with_real_registry():
    """
    - with the real registry, GET /health lists haso_queue
    """
    status, body = dispatch("GET", "/health", b"")

    assert status == 200
    assert body["status"] == "ok"
    assert "haso_queue" in body["scenarios"]


def test_post_scenario_returns_manifest(fake_scenarios, calls):
    """
    - POST /scenarios/<name> returns 200 with the scenario manifest
    - the scenario receives the parsed JSON object as params
    """
    payload = {"variant": "on_time", "namespace": "w0-abc"}

    status, body = dispatch("POST", "/scenarios/fake", json.dumps(payload).encode())

    assert status == 200
    assert body == FAKE_MANIFEST
    assert calls == [("fake", payload)]


def test_post_scenario_accepts_empty_object(fake_scenarios, calls):
    """
    - an empty JSON object is passed through as empty params
    """
    status, body = dispatch("POST", "/scenarios/fake", b"{}")

    assert status == 200
    assert calls == [("fake", {})]


def test_post_scenario_accepts_utf8_body(fake_scenarios, calls):
    """
    - a UTF-8 encoded body with non-ASCII characters is decoded
    """
    payload = {"name": "Äänekoski"}

    status, _ = dispatch(
        "POST", "/scenarios/fake", json.dumps(payload, ensure_ascii=False).encode()
    )

    assert status == 200
    assert calls == [("fake", payload)]


def test_unknown_scenario_returns_404(fake_scenarios, calls):
    """
    - POST to an unregistered scenario returns 404 with an error message
    - no scenario is invoked
    """
    response = dispatch("POST", "/scenarios/missing", b"{}")

    _assert_error(response, 404)
    assert calls == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"{", id="truncated"),
        pytest.param(b"not json", id="text"),
        pytest.param(b"\xff\xfe", id="invalid-utf8"),
        pytest.param(b"[]", id="array"),
        pytest.param(b'["on_time"]', id="array-of-string"),
        pytest.param(b'"on_time"', id="string"),
        pytest.param(b"1", id="number"),
        pytest.param(b"true", id="bool"),
        pytest.param(b"null", id="null"),
    ],
)
def test_invalid_body_returns_400(fake_scenarios, calls, body):
    """
    - a body that is not a JSON object returns 400 with an error message
    - the scenario is not invoked
    """
    response = dispatch("POST", "/scenarios/fake", body)

    _assert_error(response, 400)
    assert calls == []


def test_scenario_params_error_returns_400_with_message(fake_scenarios):
    """
    - ScenarioParamsError maps to 400 with the exception message as error
    """
    status, body = dispatch("POST", "/scenarios/bad_params", b"{}")

    assert status == 400
    assert body == {"error": "variant must be one of on_time, late"}


def test_unexpected_exception_returns_500_with_message(fake_scenarios):
    """
    - any other exception maps to 500 with an error mentioning its message
    """
    response = dispatch("POST", "/scenarios/boom", b"{}")

    _assert_error(response, 500)
    assert "database exploded" in response[1]["error"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/"),
        ("GET", "/unknown"),
        ("POST", "/unknown"),
        ("GET", "/healthz"),
        ("POST", "/scenarios"),
        ("POST", "/scenarios/"),
        ("POST", "/scenarios/fake/extra"),
        ("POST", "/scenario/fake"),
        ("GET", "/health/extra"),
    ],
)
def test_unknown_path_returns_404(fake_scenarios, calls, method, path):
    """
    - paths outside /health and /scenarios/<name> return 404
    - no scenario is invoked
    """
    response = dispatch(method, path, b"{}")

    _assert_error(response, 404)
    assert calls == []


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/health"),
        ("PUT", "/health"),
        ("DELETE", "/health"),
        ("GET", "/scenarios/fake"),
        ("PUT", "/scenarios/fake"),
        ("DELETE", "/scenarios/fake"),
        ("PATCH", "/scenarios/fake"),
    ],
)
def test_wrong_method_on_known_path_returns_405(fake_scenarios, calls, method, path):
    """
    - a known path requested with an unsupported method returns 405
    - no scenario is invoked
    """
    response = dispatch(method, path, b"{}")

    _assert_error(response, 405)
    assert calls == []


def test_haso_queue_bad_params_return_400_with_real_registry():
    """
    - invalid haso_queue params are rejected with 400 without database access
    """
    status, body = dispatch(
        "POST",
        "/scenarios/haso_queue",
        json.dumps({"variant": "bogus", "namespace": "seeder-test"}).encode(),
    )

    assert status == 400
    assert isinstance(body.get("error"), str)
