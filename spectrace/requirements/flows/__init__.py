"""Verification flows package for sequential verification with DB-cached definitions.

This module provides backward-compatible imports from the standalone spectrace-flows
package while maintaining Django-specific functionality (sync, storage).
"""

# Import from standalone spectrace-flows package
from spectrace_flows import (
    FlowDef,
    FlowParseError,
    FlowStepDef,
    SequentialFlowEngine,
    VerificationCheck,
    YAMLFlowParser,
    get_flow_by_name,
    register_flow,
)

# Django-specific imports
from requirements.flows.definitions import LINEAR_CONNECTION_FLOW, REGISTERED_FLOWS
from requirements.flows.django_storage import DjangoFlowStorage, get_engine
from requirements.flows.sync import sync_flows_to_db

__all__ = [
    # From spectrace-flows package
    "FlowDef",
    "FlowStepDef",
    "SequentialFlowEngine",
    "VerificationCheck",
    "YAMLFlowParser",
    "FlowParseError",
    "get_flow_by_name",
    "register_flow",
    # Django-specific
    "REGISTERED_FLOWS",
    "LINEAR_CONNECTION_FLOW",
    "DjangoFlowStorage",
    "get_engine",
    "sync_flows_to_db",
]
