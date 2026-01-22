"""Sequential execution engine for verification flows.

The engine executes flow steps in order, with early-exit on failure.
Each step returns a VerificationCheck and optional context updates.
"""

import importlib
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
    """

    def execute(
        self,
        flow: VerificationFlow,
        context: dict,
        source: VerificationFlowSource = VerificationFlowSource.API,
    ) -> VerificationFlowRun:
        """Execute a verification flow.

        Args:
            flow: The flow to execute (from database)
            context: Initial execution context (config, credentials, etc.)
            source: What triggered this run

        Returns:
            VerificationFlowRun with status and step results
        """
        # Create the run record
        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.RUNNING,
            context=self._sanitize_context_for_storage(context),
            source=source,
        )

        # Execute each step in order
        for i, step_def in enumerate(flow.steps):
            step_started = datetime.now(UTC)

            try:
                handler = load_handler(step_def['handler'])
                check, ctx_updates = handler(context)
            except Exception as e:
                # Handler failed to load or execute
                check = VerificationCheck(
                    name=step_def.get('name', f'step_{i}'),
                    passed=False,
                    error_message=f"Handler error: {type(e).__name__}: {str(e)}"
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
            elif hasattr(value, '__class__') and not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                # Don't try to serialize complex objects like clients
                sanitized[key] = f'[{value.__class__.__name__} instance]'
            else:
                sanitized[key] = value

        return sanitized
