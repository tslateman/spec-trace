"""Spectrace Flows - Verification flow engine for SpectTRACE.

A standalone package for executing sequential verification flows with
pluggable storage backends.

Example usage:
    from spectrace_flows import SequentialFlowEngine, FlowDef, FlowStepDef

    # Define a flow
    flow = FlowDef(
        name="api-health-check",
        display_name="API Health Check",
        description="Verify API connectivity",
        steps=[
            FlowStepDef(
                name="ping",
                handler="myapp.handlers.ping",
                display_name="Ping API",
            ),
        ],
    )

    # Execute with default in-memory storage
    engine = SequentialFlowEngine()
    result = engine.execute(flow, context={"base_url": "https://api.example.com"})

    print(f"Flow {'passed' if result.status.value == 'passed' else 'failed'}")
"""

from .definitions import (
    REGISTERED_FLOWS,
    FlowDef,
    FlowStepDef,
    get_flow_by_name,
    register_flow,
)
from .engine import (
    FlowTimeoutError,
    SequentialFlowEngine,
    StepTimeoutError,
    load_handler,
)
from .parser import FlowParseError, YAMLFlowParser
from .scenario import Fixture, Scenario, ScenarioResult
from .scenario_registry import (
    REGISTERED_SCENARIOS,
    get_scenario_by_name,
    register_scenario,
)
from .storage import FlowRunStorage, InMemoryStorage
from .types import (
    FlowRun,
    FlowSource,
    FlowStatus,
    FlowStep,
    TestConnectionResult,
    VerificationCheck,
)

__version__ = "0.1.0"

__all__ = [
    # Definitions
    "FlowDef",
    "FlowStepDef",
    "REGISTERED_FLOWS",
    "get_flow_by_name",
    "register_flow",
    # Engine
    "SequentialFlowEngine",
    "StepTimeoutError",
    "FlowTimeoutError",
    "load_handler",
    # Parser
    "YAMLFlowParser",
    "FlowParseError",
    # Scenarios
    "Fixture",
    "Scenario",
    "ScenarioResult",
    "REGISTERED_SCENARIOS",
    "get_scenario_by_name",
    "register_scenario",
    # Storage
    "FlowRunStorage",
    "InMemoryStorage",
    # Types
    "VerificationCheck",
    "FlowRun",
    "FlowStep",
    "FlowStatus",
    "FlowSource",
    "TestConnectionResult",
]
