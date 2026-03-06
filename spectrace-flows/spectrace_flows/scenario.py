"""Scenario DSL for structured test scenarios.

A Scenario describes a complete test case with four lifecycle phases:
  1. Fixtures  — shared state setup/teardown (ordered, always reversed on cleanup)
  2. setup()   — scenario-specific preparation
  3. execute() — the action under test
  4. assert_*  — outcome verification (all run; each returns a VerificationCheck)
  5. teardown()— scenario-specific cleanup (always called)

USAGE
=====
Define a Scenario subclass, declare fixtures and requirements, then implement
the lifecycle methods:

    from spectrace_flows import Scenario, Fixture, register_scenario
    from spectrace_flows.types import VerificationCheck

    class DatabaseFixture(Fixture):
        def setup(self, ctx):
            ctx["db"] = create_test_db()
            return ctx

        def teardown(self, ctx):
            ctx["db"].drop()

    @register_scenario
    class CreateUserScenario(Scenario):
        name = "create-user"
        description = "Verify user creation endpoint"
        requirements = ["REQ-USR-001"]
        fixtures = [DatabaseFixture]

        def execute(self, ctx):
            ctx["response"] = ctx["client"].post("/users/", {"name": "Alice"})

        def assert_status_201(self, ctx) -> VerificationCheck:
            return VerificationCheck(
                name="Status 201",
                passed=ctx["response"].status_code == 201,
                error_message=f"Expected 201, got {ctx['response'].status_code}",
            )

LIFECYCLE SEMANTICS
===================
- Fixtures set up in list order; torn down in reverse order.
- Teardown always runs, even if setup(), execute(), or assertions fail.
- All assert_* methods run regardless of whether earlier ones failed.
- assert_* methods are called in alphabetical order (deterministic).
- If setup() or execute() raises, assertions are skipped and error is recorded.
- assert_* methods must return a VerificationCheck; returning anything else
  records a failure for that assertion.

CONTEXT
=======
ctx is a plain dict passed through every phase. Fixtures write their state into
ctx via the dict returned from setup(). Subsequent phases read from ctx and may
add more keys. Do not store ctx state on self — ctx is the shared channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import VerificationCheck


@dataclass
class ScenarioResult:
    """Result of a scenario execution.

    Attributes:
        name: Scenario name.
        passed: True if all assertions passed and no catastrophic error occurred.
        assertions: VerificationCheck results from each assert_* method.
        error: Error message if setup() or execute() raised an exception,
               or if a fixture failed to set up.
    """

    name: str
    passed: bool
    assertions: list[VerificationCheck] = field(default_factory=list)
    error: str | None = None


class Fixture:
    """Base class for test fixtures.

    Fixtures prepare and clean up state that scenarios depend on. Define
    setup() to create state and return context updates. Define teardown()
    to release resources — it is always called, even if the scenario fails.

    Example:

        class UserFixture(Fixture):
            def setup(self, ctx):
                user = User.objects.create(email="test@example.com")
                return {"user": user}

            def teardown(self, ctx):
                ctx["user"].delete()
    """

    def setup(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Set up fixture state.

        Args:
            ctx: Current execution context.

        Returns:
            Dict of context keys to merge into ctx before the next phase.
        """
        return {}

    def teardown(self, ctx: dict[str, Any]) -> None:
        """Tear down fixture state.

        Called in reverse fixture order, always — even if the scenario failed.

        Args:
            ctx: Execution context at the point of teardown.
        """
        pass


class Scenario:
    """Base class for test scenarios.

    Class attributes:
        name:         Unique scenario identifier. Required — register_scenario
                      uses this as the registry key.
        description:  Human-readable description of what the scenario verifies.
        requirements: Requirement IDs this scenario covers (e.g. ["REQ-AUTH-001"]).
                      Enables traceability from scenario runs to requirements.
        fixtures:     Fixture subclasses to instantiate before setup(). Set up in
                      list order; torn down in reverse order.

    Override lifecycle methods as needed. Only execute() is mandatory in practice;
    all others default to no-ops.
    """

    name: str = ""
    description: str = ""
    requirements: list[str] = []
    fixtures: list[type[Fixture]] = []

    def setup(self, ctx: dict[str, Any]) -> None:
        """Prepare scenario-specific state before execution."""
        pass

    def execute(self, ctx: dict[str, Any]) -> None:
        """Perform the action under test."""
        pass

    def teardown(self, ctx: dict[str, Any]) -> None:
        """Clean up scenario-specific state. Always called."""
        pass

    def _collect_assertions(self) -> list:
        """Return assert_* methods in alphabetical order."""
        return [
            getattr(self, attr)
            for attr in sorted(dir(self.__class__))
            if attr.startswith("assert_") and callable(getattr(self, attr))
        ]

    def run(self) -> ScenarioResult:
        """Execute the full scenario lifecycle and return the result.

        Phases run in order: fixture setup → setup() → execute() → assert_* →
        teardown() → fixture teardown. Teardown always runs. All assertions run
        regardless of earlier assertion failures.

        Returns:
            ScenarioResult with pass/fail status and per-assertion details.
        """
        ctx: dict[str, Any] = {}
        fixture_instances: list[Fixture] = []
        assertions: list[VerificationCheck] = []
        catastrophic_error: str | None = None
        fixtures_ready = 0

        # Set up fixtures in order, track how many succeed
        for fixture_cls in self.fixtures:
            f = fixture_cls()
            fixture_instances.append(f)
            try:
                updates = f.setup(ctx)
                ctx.update(updates or {})
                fixtures_ready += 1
            except Exception as e:
                catastrophic_error = (
                    f"Fixture {fixture_cls.__name__}.setup() failed: {type(e).__name__}: {e}"
                )
                break

        # Run scenario phases only if all fixtures set up cleanly
        if catastrophic_error is None:
            try:
                self.setup(ctx)
                self.execute(ctx)

                for assert_fn in self._collect_assertions():
                    try:
                        check = assert_fn(ctx)
                        if not isinstance(check, VerificationCheck):
                            check = VerificationCheck(
                                name=assert_fn.__name__,
                                passed=False,
                                error_message=(
                                    f"assert_* must return VerificationCheck, "
                                    f"got {type(check).__name__}"
                                ),
                            )
                        assertions.append(check)
                    except Exception as e:
                        assertions.append(
                            VerificationCheck(
                                name=assert_fn.__name__,
                                passed=False,
                                error_message=f"{type(e).__name__}: {e}",
                            )
                        )

            except Exception as e:
                catastrophic_error = f"{type(e).__name__}: {e}"

        # Teardown: scenario first, then fixtures in reverse — always
        try:
            self.teardown(ctx)
        except Exception:
            pass

        for f in reversed(fixture_instances[:fixtures_ready]):
            try:
                f.teardown(ctx)
            except Exception:
                pass

        passed = catastrophic_error is None and all(c.passed for c in assertions)
        return ScenarioResult(
            name=self.name,
            passed=passed,
            assertions=assertions,
            error=catastrophic_error,
        )
