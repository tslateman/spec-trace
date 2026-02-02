"""Code-defined verification flow definitions.

DESIGN RATIONALE
================
Flows are defined in Python code (this file) rather than in the database.
The database stores a synced copy for visibility and queryability, but code
remains the source of truth.

Why code-defined:
- Version control: Flow changes tracked in git with full history
- Type safety: Dataclass definitions catch errors at development time
- Testability: Flow definitions available without database setup
- Deployment: New flows deploy with code, no data migrations needed
- Review: Flow changes go through normal code review

The database copy enables:
- Admin UI visibility into available flows
- Foreign key relationships for VerificationFlowRun records
- Querying flow metadata without loading Python modules

ADDING A NEW FLOW
=================
1. Define your flow as a FlowDef constant (see LINEAR_CONNECTION_FLOW example)
2. Add handler functions in requirements/flows/handlers/<your_handler>.py
3. Add the flow to REGISTERED_FLOWS list
4. Run the app -- sync_flows_to_db() runs on startup via AppConfig.ready()

Handler signature: (context: dict) -> tuple[VerificationCheck, dict]
- Receives execution context (config, credentials, client instances)
- Returns (check_result, context_updates_for_next_step)

SYNC MECHANISM
==============
On startup, sync_flows_to_db() calls update_or_create for each registered flow:
- New flows: Created in database
- Existing flows: Updated with current definition
- Removed flows: Remain in database (historical runs reference them)

The `version` field tracks intentional schema changes. Bump it when:
- Step order changes
- Steps added/removed
- Handler paths change

The `synced_at` timestamp shows when the DB was last updated from code.
"""

from dataclasses import dataclass, field


@dataclass
class FlowStepDef:
    """Definition of a single step within a verification flow.

    Attributes:
        name: Step identifier (e.g., 'config', 'auth')
        handler: Dotted path to handler function
        display_name: Human-readable step name
        description: Step description
    """
    name: str
    handler: str
    display_name: str
    description: str = ""


@dataclass
class FlowDef:
    """Definition of a complete verification flow.

    Attributes:
        name: Unique flow identifier (e.g., 'linear-connection')
        display_name: Human-readable flow name
        description: Flow description
        steps: Ordered list of step definitions
        version: Flow version for tracking changes
    """
    name: str
    display_name: str
    description: str
    steps: list[FlowStepDef] = field(default_factory=list)
    version: int = 1


LINEAR_CONNECTION_FLOW = FlowDef(
    name="linear-connection",
    display_name="Linear Connection Verification",
    description="Verify Linear API connection (config → auth → permissions)",
    steps=[
        FlowStepDef(
            name="config",
            handler="requirements.flows.handlers.linear.check_configuration",
            display_name="Configuration Check",
            description="Validate API key format and settings presence"
        ),
        FlowStepDef(
            name="auth",
            handler="requirements.flows.handlers.linear.check_authentication",
            display_name="Authentication Check",
            description="Verify API key validity with viewer query"
        ),
        FlowStepDef(
            name="permissions",
            handler="requirements.flows.handlers.linear.check_permissions",
            display_name="Permissions Check",
            description="Verify read access to issues"
        ),
    ],
    version=1,
)

REGISTERED_FLOWS: list[FlowDef] = [
    LINEAR_CONNECTION_FLOW,
]


def get_flow_by_name(name: str) -> FlowDef | None:
    """Get a flow definition by name, or None if not found."""
    return next((flow for flow in REGISTERED_FLOWS if flow.name == name), None)
