"""Sequential execution engine for verification flows.

The engine executes flow steps in order, with early-exit on failure.
Each step returns a VerificationCheck and optional context updates.
"""

import importlib
import signal
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Callable

from django.utils import timezone

from requirements.health_types import VerificationCheck
from requirements.models import (
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowSource,
    VerificationFlowStatus,
    VerificationFlowStep,
)

HandlerFunc = Callable[[dict], tuple[VerificationCheck, dict]]


class StepTimeoutError(Exception):
    """Step exceeded its timeout."""

    pass


class FlowTimeoutError(Exception):
    """Flow exceeded its total timeout."""

    pass


def load_handler(handler_path: str) -> HandlerFunc:
    """Load a handler function from its dotted path.

    Args:
        handler_path: Dotted path to handler (e.g., 'requirements.flows.handlers.linear.check_configuration')

    Returns:
        Handler function

    Raises:
        ImportError: If module cannot be imported
        AttributeError: If function doesn't exist in module
    """
    module_path, func_name = handler_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


class SequentialFlowEngine:
    """Execute verification flows as sequential steps with early-exit.

    The engine:
    1. Creates a VerificationFlowRun record
    2. Executes each step in order, recording results as VerificationFlowStep
    3. Updates context between steps (for passing data like clients)
    4. Early-exits on first failure
    5. Updates the run status based on outcome
    6. Supports per-step and per-flow timeouts (POSIX only)
    """

    @contextmanager
    def _step_timeout_context(self, seconds: int):
        """Context manager for step-level timeout.

        Uses signal.SIGALRM on POSIX systems. On Windows, timeout is not enforced.

        Args:
            seconds: Timeout in seconds

        Raises:
            StepTimeoutError: If the step exceeds the timeout
        """
        if sys.platform == 'win32' or seconds <= 0:
            # Windows doesn't support SIGALRM, skip timeout
            yield
            return

        def _timeout_handler(signum, frame):
            raise StepTimeoutError(f"Step timed out after {seconds} seconds")

        # Set up the alarm
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            # Cancel the alarm and restore old handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def execute(
        self,
        flow: VerificationFlow,
        context: dict,
        source: VerificationFlowSource = VerificationFlowSource.API,
        step_timeout: int = 60,
        flow_timeout: int = 300,
    ) -> VerificationFlowRun:
        """Execute a verification flow.

        Args:
            flow: The flow to execute (from database)
            context: Initial execution context (config, credentials, etc.)
            source: What triggered this run
            step_timeout: Maximum seconds per step (default 60)
            flow_timeout: Maximum seconds for entire flow (default 300)

        Returns:
            VerificationFlowRun with status and step results
        """
        # Import here to avoid circular import at module load
        from requirements.flows.executors import execute_step

        # Track flow start time for timeout
        flow_start = datetime.now(UTC)

        # Create the run record
        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.RUNNING,
            context=self._sanitize_context_for_storage(context),
            source=source,
        )

        # Filter out metadata entries from steps
        steps = [s for s in flow.steps if '_metadata' not in s]

        # Execute each step in order
        for i, step_def in enumerate(steps):
            # Check flow timeout
            elapsed = (datetime.now(UTC) - flow_start).total_seconds()
            if elapsed > flow_timeout:
                check = VerificationCheck(
                    name=step_def.get('name', f'step_{i}'),
                    passed=False,
                    error_message=f"Flow timed out after {flow_timeout} seconds",
                )
                VerificationFlowStep.objects.create(
                    flow_run=run,
                    step_order=i,
                    name=check.name,
                    passed=check.passed,
                    details=check.details or '',
                    error_message=check.error_message or '',
                    response_status=check.response_status,
                    response_body=check.response_body or '',
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )
                run.status = VerificationFlowStatus.FAILED
                run.completed_at = timezone.now()
                run.save()
                return run

            step_started = datetime.now(UTC)

            try:
                with self._step_timeout_context(step_timeout):
                    check, ctx_updates = execute_step(step_def, context)
            except StepTimeoutError as e:
                check = VerificationCheck(
                    name=step_def.get('name', f'step_{i}'),
                    passed=False,
                    error_message=str(e),
                )
                ctx_updates = {}
            except Exception as e:
                # Executor failed unexpectedly
                check = VerificationCheck(
                    name=step_def.get('name', f'step_{i}'),
                    passed=False,
                    error_message=f"Executor error: {type(e).__name__}: {str(e)}",
                )
                ctx_updates = {}

            step_completed = datetime.now(UTC)

            # Record the step result
            VerificationFlowStep.objects.create(
                flow_run=run,
                step_order=i,
                name=check.name,
                passed=check.passed,
                details=check.details or '',
                error_message=check.error_message or '',
                response_status=check.response_status,
                response_body=check.response_body or '',
                started_at=step_started,
                completed_at=step_completed,
            )

            # Update context for next step
            context.update(ctx_updates)

            # Early exit on failure
            if not check.passed:
                run.status = VerificationFlowStatus.FAILED
                run.completed_at = timezone.now()
                run.save()
                return run

        # All steps passed
        run.status = VerificationFlowStatus.PASSED
        run.completed_at = timezone.now()
        run.save()
        return run

    def _sanitize_context_for_storage(self, context: dict) -> dict:
        """Remove sensitive data from context before storing in DB.

        Args:
            context: Original execution context

        Returns:
            Sanitized context safe for database storage
        """
        # Keys that should not be stored in the database
        sensitive_keys = {'api_key', 'token', 'secret', 'password', 'credential'}

        sanitized = {}
        for key, value in context.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'
            elif hasattr(value, '__class__') and not isinstance(
                value, (str, int, float, bool, list, dict, type(None))
            ):
                # Don't try to serialize complex objects like clients
                sanitized[key] = f'[{value.__class__.__name__} instance]'
            else:
                sanitized[key] = value

        return sanitized
