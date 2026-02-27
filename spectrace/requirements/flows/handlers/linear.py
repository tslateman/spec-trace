"""Linear API verification flow handlers.

These handlers wrap the core health check functions to work with the flow
engine's context-based protocol. Each handler receives a context dict
and returns a VerificationCheck plus context updates.
"""

from requirements.health import (
    check_authentication as health_check_auth,
)
from requirements.health import (
    check_configuration as health_check_config,
)
from requirements.health import (
    check_permissions as health_check_perms,
)
from requirements.linear import LinearClient
from spectrace_flows import VerificationCheck


def check_configuration(context: dict) -> tuple[VerificationCheck, dict]:
    """Validate Linear configuration presence and format.

    Context required:
        api_key: Linear API key
        workspace: Workspace identifier
        team: Team identifier

    Returns:
        VerificationCheck and empty context updates
    """
    check = health_check_config(
        api_key=context.get("api_key", ""),
        workspace=context.get("workspace", ""),
        team=context.get("team", ""),
    )
    return check, {}


def check_authentication(context: dict) -> tuple[VerificationCheck, dict]:
    """Verify Linear API token validity with viewer query.

    Context required:
        api_key: Linear API key (validated in config step)

    Returns:
        VerificationCheck and context with 'client' for subsequent steps
    """
    api_key = context.get("api_key", "")
    client = LinearClient(api_key)
    check = health_check_auth(client)

    if check.passed:
        return check, {"client": client}
    return check, {}


def check_permissions(context: dict) -> tuple[VerificationCheck, dict]:
    """Verify read access to Linear issues endpoint.

    Context required:
        client: LinearClient instance (from auth step)

    Returns:
        VerificationCheck and empty context updates
    """
    client = context.get("client")

    if not client:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message="No Linear client in context (authentication step may have failed)",
        ), {}

    return health_check_perms(client), {}
