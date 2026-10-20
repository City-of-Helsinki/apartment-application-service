import pytest

from e2e.scenarios import registry
from e2e.scenarios.registry import (
    get_scenario,
    scenario,
    scenario_names,
    ScenarioParamsError,
    UnknownScenarioError,
)


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    """
    Replace the module-level scenario registry with an empty dict.

            Parameters:
                    monkeypatch: pytest monkeypatch fixture

            Returns:
                    scenarios (dict): The empty registry used by the test
    """
    scenarios = {}
    monkeypatch.setattr(registry, "_SCENARIOS", scenarios)
    return scenarios


def _manifest(params):
    """
    Return a manifest echoing the given params.

            Parameters:
                    params (dict): Scenario params

            Returns:
                    manifest (dict): {"echo": params}
    """
    return {"echo": params}


def test_scenario_decorator_registers_callable(isolated_registry):
    """
    - the decorated callable is retrievable by its name
    - the decorator returns the callable unchanged
    """
    decorated = scenario("echo")(_manifest)

    assert decorated is _manifest
    assert get_scenario("echo") is _manifest
    assert isolated_registry == {"echo": _manifest}


def test_registered_scenario_is_callable_with_params():
    """
    - the retrieved scenario is invoked with a params dict and returns a dict
    """
    scenario("echo")(_manifest)

    assert get_scenario("echo")({"a": 1}) == {"echo": {"a": 1}}


def test_scenario_decorator_as_syntax():
    """
    - the decorator works with @ syntax on a function definition
    """

    @scenario("decorated")
    def decorated(params):
        """Return an empty manifest."""
        return {}

    assert get_scenario("decorated") is decorated


def test_scenario_names_are_sorted():
    """
    - scenario_names returns every registered name in sorted order
    """
    for name in ["zeta", "alpha", "mid"]:
        scenario(name)(_manifest)

    assert scenario_names() == ["alpha", "mid", "zeta"]


def test_scenario_names_empty_registry():
    """
    - scenario_names returns an empty list when nothing is registered
    """
    assert scenario_names() == []


def test_scenario_names_returns_list():
    """
    - scenario_names returns a list, not a view of the registry
    """
    scenario("echo")(_manifest)

    names = scenario_names()

    assert isinstance(names, list)
    names.append("other")
    assert scenario_names() == ["echo"]


def test_duplicate_registration_raises_value_error():
    """
    - registering a second callable under an existing name raises ValueError
    - the original registration is kept
    """
    scenario("echo")(_manifest)

    def other(params):
        """Return an empty manifest."""
        return {}

    with pytest.raises(ValueError):
        scenario("echo")(other)

    assert get_scenario("echo") is _manifest


@pytest.mark.parametrize("name", ["missing", "", "ECHO"])
def test_get_scenario_unknown_name_raises(name):
    """
    - an unknown name raises UnknownScenarioError
    - UnknownScenarioError is a KeyError
    """
    scenario("echo")(_manifest)

    with pytest.raises(UnknownScenarioError):
        get_scenario(name)
    with pytest.raises(KeyError):
        get_scenario(name)


def test_unknown_scenario_error_is_key_error():
    """
    - UnknownScenarioError subclasses KeyError
    """
    assert issubclass(UnknownScenarioError, KeyError)


def test_scenario_params_error_is_value_error():
    """
    - ScenarioParamsError subclasses ValueError
    - its message is preserved
    """
    error = ScenarioParamsError("variant must be on_time or late")

    assert isinstance(error, ValueError)
    assert str(error) == "variant must be on_time or late"
