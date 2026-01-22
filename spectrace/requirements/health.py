"""Health check domain objects and utilities for integration verification.

This module provides dataclasses for representing health check results.
VerificationCheck represents a single check outcome, while TestConnectionResult
aggregates multiple checks into an overall connection test result.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime


def _get_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp string.

    Returns:
        Timestamp string in format 'YYYY-MM-DDTHH:MM:SS.ffffffZ'
    """
    return datetime.utcnow().isoformat() + "Z"


def _sanitize_response(response_text: str, max_length: int = 500) -> str:
    """Sanitize API response by removing credentials and truncating.

    Removes:
    - Linear API keys (lin_api_...)
    - Bearer tokens
    - Authorization header values

    Args:
        response_text: Raw response body
        max_length: Maximum length of sanitized response

    Returns:
        Sanitized response string safe for logging/storage
    """
    # Truncate first to limit processing
    sanitized = response_text[:max_length]

    # Remove API key patterns (lin_api_...)
    sanitized = re.sub(r'lin_api_[A-Za-z0-9_-]+', '[REDACTED]', sanitized)

    # Remove bearer tokens
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_.-]+', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)

    # Remove authorization headers in JSON
    sanitized = re.sub(r'"authorization":\s*"[^"]*"', '"authorization": "[REDACTED]"', sanitized, flags=re.IGNORECASE)

    if len(response_text) > max_length:
        sanitized += '... [truncated]'

    return sanitized


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
