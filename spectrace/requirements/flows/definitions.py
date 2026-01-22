"""Code-defined verification flow definitions.

Flows are defined here in Python and synced to the database on startup
for visibility. This is the source of truth for flow structure.
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
