"""Health check utilities for integration verification.

This module provides functions for verifying Linear API connectivity,
including configuration validation, authentication, and permissions checks.

Domain objects (VerificationCheck, TestConnectionResult) are imported from
health_types to avoid circular imports with the flows module.
"""

from requirements.flows.engine import SequentialFlowEngine
from requirements.health_types import (
    TestConnectionResult,
    VerificationCheck,
    _get_timestamp,
)
from requirements.linear import LinearClient
from requirements.linear_checks import (
    _sanitize_response,
    check_authentication,
    check_configuration,
    check_permissions,
)
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
