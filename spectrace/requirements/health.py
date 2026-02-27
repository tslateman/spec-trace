"""Health check utilities for integration verification.

This module provides functions for verifying Linear API connectivity,
including configuration validation, authentication, and permissions checks.

Domain objects (VerificationCheck, TestConnectionResult) are imported from
health_types to avoid circular imports with the flows module.
"""

import re

import requests

from requirements.flows.engine import SequentialFlowEngine
from requirements.health_types import (
    TestConnectionResult,
    VerificationCheck,
    _get_timestamp,
)
from requirements.linear import LinearClient
from requirements.models import VerificationFlow

# Re-export types for backward compatibility
__all__ = [
    "TestConnectionResult",
    "VerificationCheck",
    "_get_timestamp",
    "_sanitize_response",
    "check_authentication",
    "check_configuration",
    "check_permissions",
    "verify_linear_connection",
]


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
    sanitized = re.sub(r"lin_api_[A-Za-z0-9_-]+", "[REDACTED]", sanitized)

    # Remove bearer tokens
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE
    )

    # Remove authorization headers in JSON
    sanitized = re.sub(
        r'"authorization":\s*"[^"]*"',
        '"authorization": "[REDACTED]"',
        sanitized,
        flags=re.IGNORECASE,
    )

    if len(response_text) > max_length:
        sanitized += "... [truncated]"

    return sanitized


def check_configuration(api_key: str, workspace: str, team: str) -> VerificationCheck:
    """Validate Linear configuration presence and format.

    Checks:
    1. API key is present (not empty)
    2. API key matches expected format (lin_api_* prefix)
    3. Workspace identifier is present
    4. Team identifier is present

    Args:
        api_key: Linear API key (should start with 'lin_api_')
        workspace: Workspace identifier
        team: Team identifier

    Returns:
        VerificationCheck with passed=True if all config valid,
        or passed=False with specific error_message
    """
    if not api_key:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY not configured",
        )

    if not api_key.startswith("lin_api_"):
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message=(
                "LINEAR_API_KEY does not match expected format (should start with 'lin_api_')"
            ),
        )

    if not workspace:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_WORKSPACE not configured",
        )

    if not team:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_TEAM not configured",
        )

    return VerificationCheck(
        name="Configuration",
        passed=True,
        details=f"API key present, workspace: {workspace}, team: {team}",
    )


def check_authentication(client) -> VerificationCheck:
    """Verify Linear API token validity with viewer query.

    Makes actual API request to Linear using the GraphQL viewer query,
    which returns the authenticated user's info.

    Args:
        client: LinearClient instance (from requirements.linear)

    Returns:
        VerificationCheck with passed=True if authenticated,
        or passed=False with error details including status code
        and sanitized response body
    """
    try:
        result = client._execute_query("""
            query Me {
                viewer {
                    id
                    name
                    email
                }
            }
        """)

        viewer = result.get("viewer", {})
        name = viewer.get("name", "Unknown")
        email = viewer.get("email", "unknown@example.com")

        return VerificationCheck(
            name="Authentication",
            passed=True,
            details=f"Authenticated as {name} ({email})",
            response_status=200,
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Authentication failed",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text),
        )
    except ValueError as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"GraphQL error: {str(e)}",
        )
    except Exception as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}: {str(e)}",
        )


def check_permissions(client) -> VerificationCheck:
    """Verify read access to Linear issues endpoint.

    Makes a minimal GraphQL query to fetch one issue, validating
    that the API token has read permissions for issues.

    Args:
        client: LinearClient instance (from requirements.linear)

    Returns:
        VerificationCheck with passed=True if read access confirmed,
        or passed=False with error details
    """
    try:
        client._execute_query("""
            query TestIssueAccess {
                issues(first: 1) {
                    nodes {
                        id
                    }
                }
            }
        """)

        return VerificationCheck(
            name="Permissions",
            passed=True,
            details="Read access to issues endpoint confirmed",
            response_status=200,
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Insufficient permissions for issues",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text),
        )
    except ValueError as e:
        return VerificationCheck(
            name="Permissions", passed=False, error_message=f"GraphQL error: {str(e)}"
        )
    except Exception as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}: {str(e)}",
        )


def verify_linear_connection(api_key: str, workspace: str, team: str) -> TestConnectionResult:
    """Test Linear API connection with granular diagnostics.

    Runs three checks in sequence via the flow engine:
    1. Configuration: Validate settings presence and format
    2. Authentication: Verify API key with viewer query
    3. Permissions: Verify read access to issues

    Checks short-circuit on failure - if configuration fails, no API
    calls are made. If authentication fails, permissions check is skipped.

    Uses the VerificationFlow system, creating a VerificationFlowRun record
    for each execution. Falls back to direct execution if flows not synced.

    Args:
        api_key: Linear API key (lin_api_...)
        workspace: Workspace identifier
        team: Team identifier

    Returns:
        TestConnectionResult with success status, message, and checks
    """
    try:
        flow = VerificationFlow.objects.get(name="linear-connection")
    except VerificationFlow.DoesNotExist:
        return _verify_linear_connection_direct(api_key, workspace, team)

    engine = SequentialFlowEngine()
    run = engine.execute(
        flow,
        {
            "api_key": api_key,
            "workspace": workspace,
            "team": team,
        },
    )

    return TestConnectionResult.from_flow_run(run)


def _verify_linear_connection_direct(
    api_key: str, workspace: str, team: str
) -> TestConnectionResult:
    """Direct verification without flow engine (fallback when flows not synced)."""
    checks = []

    # Check 1: Configuration
    config_check = check_configuration(api_key, workspace, team)
    checks.append(config_check)
    if not config_check.passed:
        return TestConnectionResult(success=False, message="Configuration invalid", checks=checks)

    # Check 2: Authentication
    try:
        client = LinearClient(api_key)
    except Exception as e:
        return TestConnectionResult(
            success=False,
            message="Failed to create Linear client",
            checks=checks,
            error_details=f"{type(e).__name__}: {e}",
        )

    auth_check = check_authentication(client)
    checks.append(auth_check)
    if not auth_check.passed:
        return TestConnectionResult(success=False, message="Authentication failed", checks=checks)

    # Check 3: Permissions
    perm_check = check_permissions(client)
    checks.append(perm_check)

    all_passed = all(c.passed for c in checks)
    return TestConnectionResult(
        success=all_passed,
        message="All checks passed" if all_passed else "Permission check failed",
        checks=checks,
    )
