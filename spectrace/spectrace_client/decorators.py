"""Decorators for marking validation functions with requirement traceability."""

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar

from .client import ValidationClient
from .context import ValidationRun

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def verify_requirement(
    requirement_id: str,
    name: str | None = None,
    context_fn: Callable[..., dict[str, Any]] | None = None,
    client: ValidationClient | None = None,
) -> Callable[[F], F]:
    """Decorator to mark validation functions with requirement traceability.

    Automatically wraps function execution in a ValidationRun context and submits
    results to SpecTrace. Injects `validation_run` kwarg if function accepts it.

    Usage:
        @verify_requirement("REQ-PMS-OPERA-001", name="Opera PMS Connection")
        def verify_opera(hotel, validation_run: ValidationRun):
            validation_run.step("config", passed=True, details="Config found")
            validation_run.step("auth", passed=False, error_message="Login failed")
            return validation_run.result

    Args:
        requirement_id: Requirement ID (e.g., "REQ-PMS-OPERA-001")
        name: Optional human-readable name (defaults to function name)
        context_fn: Optional function to extract context from function args
                   Example: lambda hotel: {'hotel_id': hotel.id, 'vendor': 'Opera'}
        client: Optional ValidationClient (defaults to from_settings())

    Returns:
        Decorated function that auto-submits validation results
    """

    def decorator(func: F) -> F:
        validation_name = name or func.__name__

        # Check if function accepts validation_run kwarg
        sig = inspect.signature(func)
        accepts_validation_run = "validation_run" in sig.parameters

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract context from function args if context_fn provided
            context = {}
            if context_fn is not None:
                try:
                    context = context_fn(*args, **kwargs)
                except Exception as e:
                    logger.warning("Failed to extract context for %s: %s", requirement_id, e)

            # Create ValidationRun context
            validation_client = client or ValidationClient.from_settings()
            run = ValidationRun(
                requirement_id=requirement_id,
                name=validation_name,
                context=context,
                client=validation_client,
            )

            # Inject validation_run if function accepts it
            if accepts_validation_run:
                kwargs["validation_run"] = run

            # Execute function within ValidationRun context
            with run:
                result = func(*args, **kwargs)

            # Return the ValidationResult if function didn't return anything
            # or if it returned the validation_run.result
            if result is None:
                return run.result
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
