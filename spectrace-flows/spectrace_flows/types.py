"""Domain types for the flow engine.

Provides storage-agnostic data structures for representing flow execution
results. These types replace the Django models when running standalone.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def _get_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class FlowStatus(str, Enum):
    """Status of a flow run."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class FlowSource(str, Enum):
    """Source that triggered a flow run."""

    API = "api"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CLI = "cli"


@dataclass
class VerificationCheck:
    """Result of a single verification check.

    Represents the outcome of one health check operation, such as
    configuration validation, authentication, or API connectivity.

    Attributes:
        name: Check name (e.g., "Configuration", "Authentication", "API Access").
        passed: True if the check succeeded, False otherwise.
        details: Human-readable success details or status message.
        error_message: Error description when check fails.
        response_status: HTTP status code if the check involved an API request.
        response_body: Sanitized response content for debugging.
        timestamp: ISO 8601 UTC timestamp when check was performed.
    """

    name: str
    passed: bool
    details: str | None = None
    error_message: str | None = None
    response_status: int | None = None
    response_body: str | None = None
    timestamp: str = field(default_factory=_get_timestamp)


@dataclass
class FlowStep:
    """Result of a single flow step execution.

    Attributes:
        id: Unique identifier for this step (storage-assigned).
        step_order: Zero-indexed position in the flow.
        name: Step name from definition.
        passed: Whether the step passed.
        details: Success details.
        error_message: Error description if failed.
        response_status: HTTP status code if applicable.
        response_body: Response content if applicable.
        started_at: When step execution began.
        completed_at: When step execution finished.
    """

    id: str | int | None
    step_order: int
    name: str
    passed: bool
    details: str = ""
    error_message: str = ""
    response_status: int | None = None
    response_body: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class FlowRun:
    """A single execution of a verification flow.

    Attributes:
        id: Unique identifier for this run (storage-assigned).
        flow_name: Name of the flow being executed.
        status: Current status of the run.
        source: What triggered this run.
        context: Sanitized execution context.
        steps: List of step results.
        started_at: When execution began.
        completed_at: When execution finished.
    """

    id: str | int | None
    flow_name: str
    status: FlowStatus
    source: FlowSource = FlowSource.CLI
    context: dict[str, Any] = field(default_factory=dict)
    steps: list[FlowStep] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class TestConnectionResult:
    """Aggregated result of a connection test with multiple checks.

    Attributes:
        success: True if all checks passed.
        message: Human-readable summary of the test result.
        checks: List of individual VerificationCheck results.
        error_details: Details of a catastrophic error.
    """

    success: bool
    message: str
    checks: list[VerificationCheck] | None = None
    error_details: str | None = None

    @classmethod
    def from_flow_run(cls, run: FlowRun) -> "TestConnectionResult":
        """Create a TestConnectionResult from a FlowRun.

        Converts flow run data to TestConnectionResult format for
        backward compatibility with existing API responses.
        """
        checks = [
            VerificationCheck(
                name=step.name,
                passed=step.passed,
                details=step.details or None,
                error_message=step.error_message or None,
                response_status=step.response_status,
                response_body=step.response_body or None,
                timestamp=(
                    step.completed_at.isoformat().replace("+00:00", "Z")
                    if step.completed_at
                    else _get_timestamp()
                ),
            )
            for step in run.steps
        ]

        success = run.status == FlowStatus.PASSED
        if success:
            message = "All checks passed"
        elif not checks:
            message = "No checks were executed"
        else:
            failed = next((c for c in checks if not c.passed), None)
            message = f"{failed.name} failed" if failed else "Verification failed"

        return cls(
            success=success,
            message=message,
            checks=checks or None,
        )
