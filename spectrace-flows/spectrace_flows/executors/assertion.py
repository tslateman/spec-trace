"""Assertion executor for verification steps.

Checks values in context using operators (equals, contains, exists, not_empty).
Supports dot notation for nested field access.
"""

from typing import Any

from spectrace_flows.types import VerificationCheck


def _get_nested_value(data: dict, field_path: str) -> tuple[bool, Any]:
    """Get a nested value from a dict using dot notation.

    Args:
        data: Dictionary to traverse
        field_path: Dot-separated path (e.g., 'data.user.name')

    Returns:
        Tuple of (found, value). If not found, value is None.
    """
    parts = field_path.split(".")
    current = data

    for part in parts:
        if not isinstance(current, dict):
            return False, None
        if part not in current:
            return False, None
        current = current[part]

    return True, current


def execute_assertion_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Execute an assertion on a value in context.

    Config options (from step_def):
        field: Field path to check (supports dot notation, e.g., 'data.user.name')
        operator: Comparison operator (equals, contains, exists, not_empty)
        value: Expected value (for equals, contains operators)
        source: Context key to check (default: 'last_response')

    Args:
        step_def: Step definition with assertion config
        context: Execution context with source data

    Returns:
        Tuple of (VerificationCheck, {}) - assertions don't update context
    """
    step_name = step_def.get("name", "assertion")
    config = step_def.get("config", {})

    # Extract config
    field = config.get("field", "")
    operator = config.get("operator", "equals")
    expected = config.get("value")
    source_key = config.get("source", "last_response")

    # Validate operator
    valid_operators = {"equals", "contains", "exists", "not_empty"}
    if operator not in valid_operators:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=(
                    f"Unknown operator: {operator}. Valid: {', '.join(sorted(valid_operators))}"
                ),
            ),
            {},
        )

    # Get source data from context
    if source_key not in context:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=f"Source '{source_key}' not found in context",
            ),
            {},
        )

    source_data = context[source_key]

    # Handle the case where source is not a dict (e.g., it's a list or primitive)
    if not isinstance(source_data, dict):
        # If no field specified, check the source_data directly
        if not field:
            actual = source_data
            found = True
        else:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message=(
                        f"Source '{source_key}' is not a dict, cannot access field '{field}'"
                    ),
                ),
                {},
            )
    else:
        # Get the field value
        if field:
            found, actual = _get_nested_value(source_data, field)
        else:
            found, actual = True, source_data

    # Apply operator
    if operator == "exists":
        if found and actual is not None:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=True,
                    details=f"Field '{field}' exists",
                ),
                {},
            )
        else:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message=f"Field '{field}' does not exist or is None",
                ),
                {},
            )

    if operator == "not_empty":
        if found and actual:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=True,
                    details=f"Field '{field}' is not empty: {_truncate(actual)}",
                ),
                {},
            )
        else:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message=f"Field '{field}' is empty or missing",
                ),
                {},
            )

    # For equals and contains, field must exist
    if not found:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=f"Field '{field}' not found in '{source_key}'",
            ),
            {},
        )

    if operator == "equals":
        if actual == expected:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=True,
                    details=f"Field '{field}' equals '{expected}'",
                ),
                {},
            )
        else:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message=(
                        f"Field '{field}' expected '{expected}', got '{_truncate(actual)}'"
                    ),
                ),
                {},
            )

    if operator == "contains":
        if expected is None:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message="'contains' operator requires a 'value' to search for",
                ),
                {},
            )
        actual_str = str(actual) if actual is not None else ""
        expected_str = str(expected)
        if expected_str in actual_str:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=True,
                    details=f"Field '{field}' contains '{expected}'",
                ),
                {},
            )
        else:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message=(
                        f"Field '{field}' does not contain '{expected}': {_truncate(actual)}"
                    ),
                ),
                {},
            )

    # Should not reach here
    return (
        VerificationCheck(
            name=step_name,
            passed=False,
            error_message=f"Unhandled operator: {operator}",
        ),
        {},
    )


def _truncate(value: Any, max_length: int = 100) -> str:
    """Truncate a value for display in messages."""
    s = str(value)
    if len(s) > max_length:
        return s[:max_length] + "..."
    return s
