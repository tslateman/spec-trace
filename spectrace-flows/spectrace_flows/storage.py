"""Storage protocol for flow execution persistence.

Defines the abstract interface for storing flow run results.
Includes InMemoryStorage for testing and CLI usage.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from .types import FlowRun, FlowSource, FlowStatus, FlowStep, VerificationCheck


@runtime_checkable
class FlowRunStorage(Protocol):
    """Protocol for flow run persistence.

    Implementations must provide methods to create and update
    flow runs and their steps.
    """

    def create_run(
        self,
        flow_name: str,
        context: dict[str, Any],
        source: FlowSource,
    ) -> FlowRun:
        """Create a new flow run record.

        Args:
            flow_name: Name of the flow being executed.
            context: Sanitized execution context.
            source: What triggered this run.

        Returns:
            FlowRun with status=RUNNING and assigned ID.
        """
        ...

    def create_step(
        self,
        run: FlowRun,
        order: int,
        check: VerificationCheck,
        started_at: datetime,
        completed_at: datetime,
    ) -> FlowStep:
        """Record a step execution result.

        Args:
            run: The parent FlowRun.
            order: Zero-indexed step order.
            check: The verification check result.
            started_at: When step execution began.
            completed_at: When step execution finished.

        Returns:
            FlowStep with assigned ID.
        """
        ...

    def complete_run(self, run: FlowRun, status: FlowStatus) -> None:
        """Mark a flow run as complete.

        Args:
            run: The FlowRun to complete.
            status: Final status (PASSED or FAILED).
        """
        ...


class InMemoryStorage:
    """In-memory storage for testing and CLI usage.

    Stores flow runs in a dict keyed by ID. Useful for:
    - Unit testing without a database
    - CLI execution where persistence isn't needed
    - Development and debugging
    """

    def __init__(self) -> None:
        self.runs: dict[str, FlowRun] = {}
        self._step_counter: int = 0

    def create_run(
        self,
        flow_name: str,
        context: dict[str, Any],
        source: FlowSource,
    ) -> FlowRun:
        """Create a new in-memory flow run."""
        run_id = str(uuid.uuid4())
        run = FlowRun(
            id=run_id,
            flow_name=flow_name,
            status=FlowStatus.RUNNING,
            source=source,
            context=context,
            steps=[],
            started_at=datetime.now(UTC),
            completed_at=None,
        )
        self.runs[run_id] = run
        return run

    def create_step(
        self,
        run: FlowRun,
        order: int,
        check: VerificationCheck,
        started_at: datetime,
        completed_at: datetime,
    ) -> FlowStep:
        """Create a new step and add it to the run."""
        self._step_counter += 1
        step = FlowStep(
            id=self._step_counter,
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
        run.steps.append(step)
        return step

    def complete_run(self, run: FlowRun, status: FlowStatus) -> None:
        """Mark the run as complete with final status."""
        run.status = status
        run.completed_at = datetime.now(UTC)

    def get_run(self, run_id: str) -> FlowRun | None:
        """Get a run by ID (testing helper)."""
        return self.runs.get(run_id)

    def list_runs(self) -> list[FlowRun]:
        """List all runs (testing helper)."""
        return list(self.runs.values())
