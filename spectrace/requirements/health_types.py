"""Health check domain objects for integration verification (Django integration).

This module re-exports types from the standalone spectrace-flows package
and adds Django-specific functionality like from_flow_run() that uses
Django ORM.
"""

# Re-export from standalone package for backward compatibility
from spectrace_flows import TestConnectionResult as BaseTestConnectionResult
from spectrace_flows import VerificationCheck
from spectrace_flows.types import _get_timestamp

__all__ = ["VerificationCheck", "TestConnectionResult", "_get_timestamp"]


class TestConnectionResult(BaseTestConnectionResult):
    """Extended TestConnectionResult with Django ORM integration."""

    @classmethod
    def from_flow_run(cls, run) -> "TestConnectionResult":
        """Create a TestConnectionResult from a VerificationFlowRun.

        Converts flow run data back to the TestConnectionResult format
        for backward compatibility with existing API responses.

        Args:
            run: VerificationFlowRun instance (Django model)

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
                timestamp=(
                    step.completed_at.isoformat().replace("+00:00", "Z")
                    if step.completed_at
                    else _get_timestamp()
                ),
            )
            for step in run.steps.all().order_by("step_order")
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
