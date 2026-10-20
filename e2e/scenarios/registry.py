"""
Registry of named e2e scenarios.

A scenario is a callable taking a params dict and returning a
JSON-serializable manifest describing what it seeded. Scenarios register
themselves with the @scenario decorator when their module is imported
(see e2e/scenarios/__init__.py).
"""

_SCENARIOS = {}


class UnknownScenarioError(KeyError):
    """
    Raised when no scenario is registered under the requested name.
    """


class ScenarioParamsError(ValueError):
    """
    Raised by a scenario when its params are invalid; the message is shown
    to the caller.
    """


def scenario(name):
    """
    Return a decorator registering a callable as the scenario of a name.

            Parameters:
                    name (str): Scenario name used in the seeder URL

            Returns:
                    decorator (callable): Registers and returns the callable
                    unchanged; raises ValueError if the name is taken
    """

    def decorator(func):
        """
        Register func under the name and return it unchanged.

                Parameters:
                        func (callable): func(params) -> manifest

                Returns:
                        func (callable): The same callable
        """
        if name in _SCENARIOS:
            raise ValueError(f"Scenario {name!r} is already registered")
        _SCENARIOS[name] = func
        return func

    return decorator


def get_scenario(name):
    """
    Return the scenario registered under a name.

            Parameters:
                    name (str): Scenario name

            Returns:
                    scenario (callable): The registered callable

            Raises:
                    UnknownScenarioError: If no scenario has the name
    """
    try:
        return _SCENARIOS[name]
    except KeyError:
        raise UnknownScenarioError(name) from None


def scenario_names():
    """
    Return the names of all registered scenarios.

            Returns:
                    names (list[str]): Sorted scenario names
    """
    return sorted(_SCENARIOS)
