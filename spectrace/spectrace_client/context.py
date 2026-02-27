"""Context manager for multi-step validation runs."""

import logging
import time
from datetime import datetime
from typing import Any

from .client import ValidationClient
from .models import ValidationResult, ValidationStatus, ValidationStep

logger = logging.getLogger(__name__)


class ValidationRun:
    """Context manager for multi-step validation runs.

    Usage:
        with ValidationRun("REQ-PMS-001", "PMS Connection") as run:
            run.step("config", passed=True, details="Config found")
            run.step("auth", passed=False, error_message="Login failed")
        # Auto-submits to SpecTrace on __exit__
    """

    def __init__(
        self,
        requirement_id: str,
        name: str,
        context: dict[str, Any] | None = None,
        client: ValidationClient | None = None,
    ):
        """Initialize validation run.

        Args:
            requirement_id: Requirement ID (e.g., "REQ-PMS-OPERA-001")
            name: Human-readable validation name
            context: Optional context dict (hotel_id, vendor, etc.)
            client: Optional ValidationClient (defaults to from_settings())
        """
        self.requirement_id = requirement_id
        self.name = name
        self.context = context or {}
        self.client = client or ValidationClient.from_settings()

        self.steps: list[ValidationStep] = []
        self.result: ValidationResult | None = None
        self.start_time: float | None = None

    def __enter__(self) -> "ValidationRun":
        """Enter context manager, start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager, compute status, and submit to SpecTrace.

        Returns:
            False (doesn't suppress exceptions)
        """
        # Compute overall status
        if exc_type is not None:
            # Exception during validation
            status = ValidationStatus.ERROR
            message = f"Validation error: {exc_val}"
        else:
            status = self._compute_status()
            message = self._compute_message()

        self.result = ValidationResult(
            requirement_id=self.requirement_id,
            name=self.name,
            status=status,
            steps=self.steps,
            message=message,
            context=self.context,
            timestamp=datetime.now(),
        )

        # Submit to SpecTrace (best-effort, log on failure)
        try:
            self.client.submit_validation(self.result)
        except Exception as e:
            logger.warning(
                "Failed to submit validation for %s: %s",
                self.requirement_id,
                e,
                exc_info=True,
            )

        # Don't suppress exceptions
        return False

    def step(
        self,
        name: str,
        passed: bool,
        details: str = "",
        error_message: str = "",
        duration_ms: int | None = None,
    ) -> None:
        """Add a validation step result.

        Args:
            name: Step name (e.g., "configuration", "authentication")
            passed: Whether the step passed
            details: Optional success details
            error_message: Optional error message (if passed=False)
            duration_ms: Optional step duration in milliseconds
        """
        step = ValidationStep(
            name=name,
            passed=passed,
            details=details,
            error_message=error_message,
            duration_ms=duration_ms,
            timestamp=datetime.now(),
        )
        self.steps.append(step)

    def _compute_status(self) -> ValidationStatus:
        """Compute overall status from steps.

        Returns:
            SUCCESS if all steps passed
            DEGRADED if some steps passed, some failed
            FAILURE if all steps failed
            SUCCESS if no steps (empty validation)
        """
        if not self.steps:
            return ValidationStatus.SUCCESS

        passed_count = sum(1 for s in self.steps if s.passed)
        failed_count = len(self.steps) - passed_count

        if failed_count == 0:
            return ValidationStatus.SUCCESS
        elif passed_count > 0:
            return ValidationStatus.DEGRADED
        else:
            return ValidationStatus.FAILURE

    def _compute_message(self) -> str:
        """Generate human-readable summary message.

        Returns:
            Message summarizing validation results
        """
        if not self.steps:
            return "Validation completed"

        passed = sum(1 for s in self.steps if s.passed)
        failed = len(self.steps) - passed

        if failed == 0:
            return f"All {len(self.steps)} checks passed"
        elif passed == 0:
            return f"All {len(self.steps)} checks failed"
        else:
            return f"{passed} passed, {failed} failed"
