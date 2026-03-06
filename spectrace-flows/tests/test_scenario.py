"""Tests for the Scenario DSL.

Tests cover:
- Happy path: all assertions pass
- Partial failure: some assertions fail
- No assertions: vacuously passes
- Catastrophic error in setup() / execute()
- Fixture setup/teardown ordering
- Fixture teardown on failure
- Fixture setup failure: only teardown successfully-set-up fixtures
- assert_* discovery and alphabetical ordering
- Incorrect return type from assert_* method
- Exception raised inside assert_* method
- Teardown always runs, even on execute() failure
- register_scenario decorator and get_scenario_by_name
- register_scenario rejects empty name
- register_scenario replaces existing entry
- Requirement linkage on scenario class
"""

import pytest

from spectrace_flows.scenario import Fixture, Scenario, ScenarioResult
from spectrace_flows.scenario_registry import (
    get_scenario_by_name,
    register_scenario,
)
from spectrace_flows.types import VerificationCheck


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class PassingScenario(Scenario):
    name = "passing"

    def execute(self, ctx):
        ctx["value"] = 42

    def assert_value_set(self, ctx) -> VerificationCheck:
        return VerificationCheck(name="value set", passed=ctx.get("value") == 42)


class FailingAssertionScenario(Scenario):
    name = "failing-assertion"

    def assert_always_fails(self, ctx) -> VerificationCheck:
        return VerificationCheck(name="always fails", passed=False, error_message="nope")

    def assert_always_passes(self, ctx) -> VerificationCheck:
        return VerificationCheck(name="always passes", passed=True)


class NoAssertionScenario(Scenario):
    name = "no-assertions"

    def execute(self, ctx):
        ctx["ran"] = True


class SetupFailureScenario(Scenario):
    name = "setup-failure"

    def setup(self, ctx):
        raise RuntimeError("setup exploded")

    def assert_never_reached(self, ctx) -> VerificationCheck:
        return VerificationCheck(name="never reached", passed=True)


class ExecuteFailureScenario(Scenario):
    name = "execute-failure"

    def execute(self, ctx):
        raise ValueError("execute exploded")

    def assert_never_reached(self, ctx) -> VerificationCheck:
        return VerificationCheck(name="never reached", passed=True)


class TeardownTrackingScenario(Scenario):
    name = "teardown-tracking"

    def execute(self, ctx):
        raise RuntimeError("forced failure")

    def teardown(self, ctx):
        ctx["teardown_ran"] = True


class WrongReturnTypeScenario(Scenario):
    name = "wrong-return-type"

    def assert_returns_string(self, ctx) -> VerificationCheck:
        return "not a VerificationCheck"  # type: ignore[return-value]


class AssertionExceptionScenario(Scenario):
    name = "assertion-exception"

    def assert_raises(self, ctx) -> VerificationCheck:
        raise KeyError("missing key")


class AlphabeticalOrderScenario(Scenario):
    name = "alphabetical-order"
    _call_order: list[str] = []

    def assert_b_second(self, ctx) -> VerificationCheck:
        ctx.setdefault("order", []).append("b")
        return VerificationCheck(name="b", passed=True)

    def assert_a_first(self, ctx) -> VerificationCheck:
        ctx.setdefault("order", []).append("a")
        return VerificationCheck(name="a", passed=True)

    def assert_c_third(self, ctx) -> VerificationCheck:
        ctx.setdefault("order", []).append("c")
        return VerificationCheck(name="c", passed=True)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


class OrderTrackingFixture(Fixture):
    def __init__(self, label: str, log: list):
        self.label = label
        self.log = log

    def setup(self, ctx):
        self.log.append(f"setup:{self.label}")
        return {f"fixture_{self.label}": True}

    def teardown(self, ctx):
        self.log.append(f"teardown:{self.label}")


class FailingSetupFixture(Fixture):
    def __init__(self, log: list):
        self.log = log

    def setup(self, ctx):
        self.log.append("setup:failing")
        raise RuntimeError("fixture setup failed")

    def teardown(self, ctx):
        self.log.append("teardown:failing")


class FailingTeardownFixture(Fixture):
    def setup(self, ctx):
        return {"ft": True}

    def teardown(self, ctx):
        raise RuntimeError("teardown error — should be swallowed")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run__passes_when_all_assertions_pass():
    result = PassingScenario().run()
    assert result.passed is True
    assert result.error is None
    assert len(result.assertions) == 1
    assert result.assertions[0].passed is True


def test_run__returns_scenario_result():
    result = PassingScenario().run()
    assert isinstance(result, ScenarioResult)
    assert result.name == "passing"


def test_run__no_assertions_passes_vacuously():
    result = NoAssertionScenario().run()
    assert result.passed is True
    assert result.assertions == []
    assert result.error is None


# ---------------------------------------------------------------------------
# Assertion failures
# ---------------------------------------------------------------------------


def test_run__fails_when_any_assertion_fails():
    result = FailingAssertionScenario().run()
    assert result.passed is False


def test_run__all_assertions_run_despite_earlier_failure():
    result = FailingAssertionScenario().run()
    names = [c.name for c in result.assertions]
    assert "always fails" in names
    assert "always passes" in names


def test_run__collects_all_assertion_results():
    result = FailingAssertionScenario().run()
    assert len(result.assertions) == 2
    failing = next(c for c in result.assertions if c.name == "always fails")
    passing = next(c for c in result.assertions if c.name == "always passes")
    assert failing.passed is False
    assert passing.passed is True


# ---------------------------------------------------------------------------
# Catastrophic errors
# ---------------------------------------------------------------------------


def test_run__records_error_when_setup_raises():
    result = SetupFailureScenario().run()
    assert result.passed is False
    assert result.error is not None
    assert "RuntimeError" in result.error
    assert "setup exploded" in result.error


def test_run__skips_assertions_when_setup_raises():
    result = SetupFailureScenario().run()
    assert result.assertions == []


def test_run__records_error_when_execute_raises():
    result = ExecuteFailureScenario().run()
    assert result.passed is False
    assert result.error is not None
    assert "ValueError" in result.error
    assert "execute exploded" in result.error


def test_run__skips_assertions_when_execute_raises():
    result = ExecuteFailureScenario().run()
    assert result.assertions == []


# ---------------------------------------------------------------------------
# Teardown always runs
# ---------------------------------------------------------------------------


def test_run__teardown_runs_even_when_execute_fails():
    scenario = TeardownTrackingScenario()
    ctx_spy = {}

    original_teardown = scenario.teardown

    def capturing_teardown(ctx):
        original_teardown(ctx)
        ctx_spy.update(ctx)

    scenario.teardown = capturing_teardown
    scenario.run()

    assert ctx_spy.get("teardown_ran") is True


# ---------------------------------------------------------------------------
# Incorrect return type from assert_*
# ---------------------------------------------------------------------------


def test_run__wrong_return_type_records_failure():
    result = WrongReturnTypeScenario().run()
    assert result.passed is False
    assert len(result.assertions) == 1
    check = result.assertions[0]
    assert check.passed is False
    assert check.error_message is not None
    assert "VerificationCheck" in check.error_message


# ---------------------------------------------------------------------------
# Exception inside assert_*
# ---------------------------------------------------------------------------


def test_run__exception_in_assertion_recorded_as_failure():
    result = AssertionExceptionScenario().run()
    assert result.passed is False
    assert len(result.assertions) == 1
    check = result.assertions[0]
    assert check.passed is False
    assert check.error_message is not None
    assert "KeyError" in check.error_message


# ---------------------------------------------------------------------------
# Alphabetical ordering of assert_* methods
# ---------------------------------------------------------------------------


def test_run__assertions_run_in_alphabetical_order():
    result = AlphabeticalOrderScenario().run()
    names = [c.name for c in result.assertions]
    assert names == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def test_run__fixtures_set_up_in_order():
    log: list[str] = []

    class MultiFixtureScenario(Scenario):
        name = "multi-fixture"
        fixtures = [
            type("F1", (OrderTrackingFixture,), {}),
            type("F2", (OrderTrackingFixture,), {}),
        ]

    # Build with actual instances using closures
    log_ref = log

    class F1(Fixture):
        def setup(self, ctx):
            log_ref.append("setup:F1")
            return {}

        def teardown(self, ctx):
            log_ref.append("teardown:F1")

    class F2(Fixture):
        def setup(self, ctx):
            log_ref.append("setup:F2")
            return {}

        def teardown(self, ctx):
            log_ref.append("teardown:F2")

    class OrderedScenario(Scenario):
        name = "ordered"
        fixtures = [F1, F2]

    OrderedScenario().run()

    setup_indices = [log.index("setup:F1"), log.index("setup:F2")]
    assert setup_indices[0] < setup_indices[1], "F1 should set up before F2"


def test_run__fixtures_torn_down_in_reverse_order():
    log: list[str] = []
    log_ref = log

    class F1(Fixture):
        def setup(self, ctx):
            log_ref.append("setup:F1")
            return {}

        def teardown(self, ctx):
            log_ref.append("teardown:F1")

    class F2(Fixture):
        def setup(self, ctx):
            log_ref.append("setup:F2")
            return {}

        def teardown(self, ctx):
            log_ref.append("teardown:F2")

    class OrderedScenario(Scenario):
        name = "ordered-td"
        fixtures = [F1, F2]

    OrderedScenario().run()

    td_f1 = log.index("teardown:F1")
    td_f2 = log.index("teardown:F2")
    assert td_f2 < td_f1, "F2 should tear down before F1 (reverse order)"


def test_run__fixture_context_available_in_scenario():
    class ContextFixture(Fixture):
        def setup(self, ctx):
            return {"injected": "hello"}

    class ContextScenario(Scenario):
        name = "ctx-scenario"
        fixtures = [ContextFixture]

        def assert_injected(self, ctx) -> VerificationCheck:
            return VerificationCheck(
                name="injected value",
                passed=ctx.get("injected") == "hello",
            )

    result = ContextScenario().run()
    assert result.passed is True


def test_run__fixture_setup_failure_records_error():
    log: list[str] = []

    class FailFirst(Fixture):
        def setup(self, ctx):
            log.append("setup:FailFirst")
            raise RuntimeError("first fixture broken")

        def teardown(self, ctx):
            log.append("teardown:FailFirst")

    class NeverReached(Fixture):
        def setup(self, ctx):
            log.append("setup:NeverReached")
            return {}

        def teardown(self, ctx):
            log.append("teardown:NeverReached")

    class BrokenScenario(Scenario):
        name = "broken-fixture"
        fixtures = [FailFirst, NeverReached]

    result = BrokenScenario().run()
    assert result.passed is False
    assert result.error is not None
    assert "FailFirst" in result.error
    assert "first fixture broken" in result.error


def test_run__only_teardown_successfully_setup_fixtures_on_failure():
    log: list[str] = []

    class GoodFixture(Fixture):
        def setup(self, ctx):
            log.append("setup:Good")
            return {}

        def teardown(self, ctx):
            log.append("teardown:Good")

    class BreakingFixture(Fixture):
        def setup(self, ctx):
            log.append("setup:Breaking")
            raise RuntimeError("boom")

        def teardown(self, ctx):
            log.append("teardown:Breaking")

    class MixedFixtureScenario(Scenario):
        name = "mixed-fixture"
        fixtures = [GoodFixture, BreakingFixture]

    MixedFixtureScenario().run()

    assert "teardown:Good" in log
    assert "teardown:Breaking" not in log


def test_run__fixture_teardown_exception_does_not_propagate():
    class ScenarioWithBadTeardown(Scenario):
        name = "bad-td"
        fixtures = [FailingTeardownFixture]

        def assert_passes(self, ctx) -> VerificationCheck:
            return VerificationCheck(name="ok", passed=True)

    # Should not raise
    result = ScenarioWithBadTeardown().run()
    assert result.passed is True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_register_scenario__decorator_registers_class():
    @register_scenario
    class MyScenario(Scenario):
        name = "registry-test-decorator"

    found = get_scenario_by_name("registry-test-decorator")
    assert found is MyScenario


def test_register_scenario__returns_class_unchanged():
    class MyScenario(Scenario):
        name = "registry-test-return"

    result = register_scenario(MyScenario)
    assert result is MyScenario


def test_register_scenario__replaces_existing_entry():
    class V1(Scenario):
        name = "registry-test-replace"
        description = "v1"

    class V2(Scenario):
        name = "registry-test-replace"
        description = "v2"

    register_scenario(V1)
    register_scenario(V2)

    found = get_scenario_by_name("registry-test-replace")
    assert found is V2
    assert found.description == "v2"


def test_register_scenario__raises_on_empty_name():
    class NoName(Scenario):
        name = ""

    with pytest.raises(ValueError, match="non-empty name"):
        register_scenario(NoName)


def test_get_scenario_by_name__returns_none_for_unknown():
    assert get_scenario_by_name("does-not-exist-xyz") is None


# ---------------------------------------------------------------------------
# Requirement linkage
# ---------------------------------------------------------------------------


def test_scenario__requirements_accessible():
    class TracedScenario(Scenario):
        name = "traced"
        requirements = ["REQ-001", "REQ-002"]

    assert TracedScenario.requirements == ["REQ-001", "REQ-002"]


def test_scenario__empty_requirements_by_default():
    class UnlinkedScenario(Scenario):
        name = "unlinked"

    assert UnlinkedScenario.requirements == []
