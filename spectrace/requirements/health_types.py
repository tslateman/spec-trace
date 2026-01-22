"""Health check domain objects for integration verification.

This module provides pure dataclasses for representing health check results,
extracted to avoid circular imports between health.py and flows/engine.py.

VerificationCheck represents a single check outcome, while TestConnectionResult
aggregates multiple checks into an overall connection test result.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _get_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp string.

    Returns:
        Timestamp string in format 'YYYY-MM-DDTHH:MM:SS.ffffffZ'
    """
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class VerificationCheck:
    """Result of a single verification check.

    Represents the outcome of one health check operation, such as
    configuration validation, authentication, or API connectivity.

    Attributes:
        name: Check name (e.g., "Configuration", "Authentication", "API Access").
        passed: True if the check succeeded, False otherwise.
        details: Human-readable success details or status message.
        error_message: Error description when check fails (HEALTH-04).
        response_status: HTTP status code if the check involved an API request.
        response_body: Sanitized response content for debugging (HEALTH-04).
            Should never contain API keys or sensitive credentials.
        timestamp: ISO 8601 UTC timestamp when check was performed.
            Auto-generated per instance.
    """

    name: str
    passed: bool
    details: str | None = None
    error_message: str | None = None
    response_status: int | None = None
    response_body: str | None = None
    timestamp: str = field(default_factory=_get_timestamp)


@dataclass
class TestConnectionResult:
    """Aggregated result of a connection test with multiple checks.

    Represents the overall outcome of testing a connection to an external
    service (e.g., Linear API), combining multiple individual checks.

    Attributes:
        success: True if all checks passed, False otherwise.
        message: Human-readable summary of the test result.
        checks: List of individual VerificationCheck results.
            May be None if a catastrophic error prevented checks from running.
        error_details: Details of a catastrophic error that prevented
            the checks from completing (e.g., network unreachable).
    """

    success: bool
    message: str
    checks: list[VerificationCheck] | None = None
    error_details: str | None = None

    @classmethod
    def from_flow_run(cls, run) -> 'TestConnectionResult':
        """Create a TestConnectionResult from a VerificationFlowRun.

        Converts flow run data back to the TestConnectionResult format
        for backward compatibility with existing API responses.

        Args:
            run: VerificationFlowRun instance

        Returns:
            TestConnectionResult with checks populated from flow steps
        """
        # Import here to avoid circular import with models
        from requirements.models import VerificationFlowStatus

        checks = [
            VerificationCheck(
                name=step.name,
                passed=step.passed,
                details=step.details or None,
                error_message=step.error_message or None,
                response_status=step.response_status,
                response_body=step.response_body or None,
                timestamp=step.completed_at.isoformat().replace("+00:00", "Z") if step.completed_at else _get_timestamp(),
            )
            for step in run.steps.all().order_by('step_order')
        ]

        success = run.status == VerificationFlowStatus.PASSED
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
