"""Code-defined verification flow definitions for Django integration.

This module defines Django-specific flows that use handlers from the Django app.
It re-exports types from the standalone spectrace-flows package for convenience.

ADDING A NEW FLOW
=================
1. Define your flow as a FlowDef constant (see LINEAR_CONNECTION_FLOW example)
2. Add handler functions in requirements/flows/handlers/<your_handler>.py
3. Add the flow to REGISTERED_FLOWS list
4. Run the app -- sync_flows_to_db() runs on startup via AppConfig.ready()

Handler signature: (context: dict) -> tuple[VerificationCheck, dict]
- Receives execution context (config, credentials, client instances)
- Returns (check_result, context_updates_for_next_step)
"""

# Re-export from standalone package for backward compatibility
from spectrace_flows import FlowDef, FlowStepDef, get_flow_by_name, register_flow

# Django-specific flow definitions using Django handlers
LINEAR_CONNECTION_FLOW = FlowDef(
    name="linear-connection",
    display_name="Linear Connection Verification",
    description="Verify Linear API connection (config → auth → permissions)",
    steps=[
        FlowStepDef(
            name="config",
            handler="requirements.flows.handlers.linear.check_configuration",
            display_name="Configuration Check",
            description="Validate API key format and settings presence",
        ),
        FlowStepDef(
            name="auth",
            handler="requirements.flows.handlers.linear.check_authentication",
            display_name="Authentication Check",
            description="Verify API key validity with viewer query",
        ),
        FlowStepDef(
            name="permissions",
            handler="requirements.flows.handlers.linear.check_permissions",
            display_name="Permissions Check",
            description="Verify read access to issues",
        ),
    ],
    version=1,
)

# Local registry for Django-defined flows
REGISTERED_FLOWS: list[FlowDef] = [
    LINEAR_CONNECTION_FLOW,
]


def register_django_flows() -> None:
    """Register Django flows with the spectrace-flows package.

    Call this at app startup to make Django-defined flows
    available to the standalone engine.
    """
    for flow in REGISTERED_FLOWS:
        register_flow(flow)
