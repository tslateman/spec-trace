"""Registry for Scenario classes.

Mirrors the pattern used by definitions.py for FlowDef — scenarios are
registered in code, giving version control, type safety, and deployment
without data migrations.

USAGE
=====
Use register_scenario as a class decorator:

    @register_scenario
    class MyScenario(Scenario):
        name = "my-scenario"
        ...

Or register explicitly after definition:

    register_scenario(MyScenario)

The registry key is Scenario.name. Registering a scenario with a name that
already exists replaces the previous entry.
"""

from __future__ import annotations

from .scenario import Scenario

REGISTERED_SCENARIOS: list[type[Scenario]] = []


def register_scenario(cls: type[Scenario]) -> type[Scenario]:
    """Register a Scenario class.

    Usable as a class decorator or called directly. Replaces any existing
    scenario with the same name.

    Args:
        cls: A Scenario subclass with a non-empty name attribute.

    Returns:
        The class unchanged (enables use as a decorator).

    Raises:
        ValueError: If cls.name is empty.
    """
    if not cls.name:
        raise ValueError(f"Scenario class {cls.__name__} must define a non-empty name attribute")
    global REGISTERED_SCENARIOS
    REGISTERED_SCENARIOS = [s for s in REGISTERED_SCENARIOS if s.name != cls.name]
    REGISTERED_SCENARIOS.append(cls)
    return cls


def get_scenario_by_name(name: str) -> type[Scenario] | None:
    """Return the registered Scenario class with the given name, or None."""
    return next((s for s in REGISTERED_SCENARIOS if s.name == name), None)
