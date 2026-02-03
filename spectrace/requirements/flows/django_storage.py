"""Django ORM storage backend for spectrace-flows.

Implements the FlowRunStorage protocol using Django models for persistence.
"""

from datetime import datetime
from typing import Any

from django.utils import timezone

from requirements.models import (
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowSource,
    VerificationFlowStatus,
    VerificationFlowStep,
)
from spectrace_flows.storage import FlowRunStorage
from spectrace_flows.types import (
    FlowRun,
    FlowSource,
    FlowStatus,
    FlowStep,
    VerificationCheck,
)


# Map spectrace_flows.FlowSource to Django model enum
SOURCE_MAP = {
    FlowSource.API: VerificationFlowSource.API,
    FlowSource.MANUAL: VerificationFlowSource.MANUAL,
    FlowSource.SCHEDULED: VerificationFlowSource.SCHEDULED,
    FlowSource.CLI: VerificationFlowSource.API,  # CLI maps to API source in Django
}

# Map spectrace_flows.FlowStatus to Django model enum
# Note: Django model doesn't have PENDING, so we map it to RUNNING
STATUS_MAP = {
    FlowStatus.PENDING: VerificationFlowStatus.RUNNING,
    FlowStatus.RUNNING: VerificationFlowStatus.RUNNING,
    FlowStatus.PASSED: VerificationFlowStatus.PASSED,
    FlowStatus.FAILED: VerificationFlowStatus.FAILED,
}


class DjangoFlowStorage(FlowRunStorage):
    """Django ORM implementation of FlowRunStorage.

    Stores flow runs and steps using VerificationFlowRun and
    VerificationFlowStep Django models.
    """

    def create_run(
        self,
        flow_name: str,
        context: dict[str, Any],
        source: FlowSource,
    ) -> FlowRun:
        """Create a new flow run record in the database.

        Args:
            flow_name: Name of the flow being executed.
            context: Sanitized execution context.
            source: What triggered this run.

        Returns:
            FlowRun wrapping the created Django model instance.
        """
        # Look up the VerificationFlow by name
        flow = VerificationFlow.objects.get(name=flow_name)

        # Create the run record
        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.RUNNING,
            context=context,
            source=SOURCE_MAP.get(source, VerificationFlowSource.API),
        )

        # Return a FlowRun dataclass wrapping the model
        return FlowRun(
            id=run.pk,
            flow_name=flow_name,
            status=FlowStatus.RUNNING,
            source=source,
            context=context,
            steps=[],
            started_at=run.started_at,
            completed_at=None,
        )

    def create_step(
        self,
        run: FlowRun,
        order: int,
        check: VerificationCheck,
        started_at: datetime,
        completed_at: datetime,
    ) -> FlowStep:
        """Record a step execution result in the database.

        Args:
            run: The parent FlowRun.
            order: Zero-indexed step order.
            check: The verification check result.
            started_at: When step execution began.
            completed_at: When step execution finished.

        Returns:
            FlowStep wrapping the created Django model instance.
        """
        # Create the step record
        step = VerificationFlowStep.objects.create(
            flow_run_id=run.id,
            step_order=order,
            name=check.name,
            passed=check.passed,
            details=check.details or "",
            error_message=check.error_message or "",
            response_status=check.response_status,
            response_body=check.response_body or "",
            started_at=started_at,
            completed_at=completed_at,
        )

        # Create FlowStep dataclass
        flow_step = FlowStep(
            id=step.pk,
            step_order=order,
            name=check.name,
            passed=check.passed,
            details=check.details or "",
            error_message=check.error_message or "",
            response_status=check.response_status,
            response_body=check.response_body or "",
            started_at=started_at,
            completed_at=completed_at,
        )

        # Add to run's steps list
        run.steps.append(flow_step)

        return flow_step

    def complete_run(self, run: FlowRun, status: FlowStatus) -> None:
        """Mark a flow run as complete in the database.

        Args:
            run: The FlowRun to complete.
            status: Final status (PASSED or FAILED).
        """
        # Update the Django model
        VerificationFlowRun.objects.filter(pk=run.id).update(
            status=STATUS_MAP.get(status, VerificationFlowStatus.FAILED),
            completed_at=timezone.now(),
        )

        # Update the FlowRun dataclass
        run.status = status
        run.completed_at = timezone.now()


def get_engine():
    """Get a SequentialFlowEngine configured with Django storage.

    Returns:
        SequentialFlowEngine using DjangoFlowStorage backend.
    """
    from spectrace_flows import SequentialFlowEngine

    return SequentialFlowEngine(storage=DjangoFlowStorage())
