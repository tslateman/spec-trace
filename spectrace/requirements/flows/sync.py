"""Sync code-defined flows to the database.

This module syncs flow definitions from Python code to the database
on startup, making them visible for querying while keeping the code
as the source of truth.

Also supports syncing YAML-defined flows via sync_yaml_flows_to_db().
"""

import logging
from dataclasses import asdict

from django.utils import timezone

from spectrace_flows import FlowDef

from requirements.flows.definitions import REGISTERED_FLOWS, register_django_flows
from requirements.models import Requirement, VerificationFlow

logger = logging.getLogger(__name__)


def sync_flows_to_db() -> dict[str, str]:
    """Sync all registered flows from code to database.

    Creates new flows or updates existing ones based on name.
    Returns a dict of flow names to actions taken.

    Returns:
        Dict mapping flow name to action ('created' or 'updated')
    """
    results = {}

    for flow_def in REGISTERED_FLOWS:
        # Convert step definitions to dicts for JSON storage
        steps_data = [asdict(step) for step in flow_def.steps]

        flow, created = VerificationFlow.objects.update_or_create(
            name=flow_def.name,
            defaults={
                'display_name': flow_def.display_name,
                'description': flow_def.description,
                'steps': steps_data,
                'version': flow_def.version,
                'synced_at': timezone.now(),
            }
        )

        action = 'created' if created else 'updated'
        results[flow_def.name] = action
        logger.info(f"Flow '{flow_def.name}' {action} (v{flow_def.version})")

    return results


def sync_flows_safe() -> dict[str, str] | None:
    """Safely sync flows, handling database errors gracefully.

    Useful for calling during app startup when the database
    might not be ready (e.g., during migrations).

    Returns:
        Dict of results if successful, None if sync failed
    """
    try:
        # Register Django flows with the standalone package
        register_django_flows()
        return sync_flows_to_db()
    except Exception as e:
        logger.warning(f"Could not sync flows to database: {e}")
        return None


def _sync_flow_requirements(
    flow: VerificationFlow,
    requirement_ids: list[str],
) -> dict[str, list[str]]:
    """Link requirements to a flow via M2M relationship.

    Looks up requirements by external_id and links them to the flow.
    Missing requirements are logged as warnings (not errors).

    Args:
        flow: The VerificationFlow to link requirements to
        requirement_ids: List of requirement external_ids (e.g., ['REQ-001', 'REQ-002'])

    Returns:
        Dict with 'linked' and 'missing' lists of requirement IDs
    """
    if not requirement_ids:
        flow.requirements.clear()
        return {'linked': [], 'missing': []}

    linked = []
    missing = []
    requirements_to_link = []

    for req_id in requirement_ids:
        try:
            req = Requirement.objects.get(external_id=req_id)
            requirements_to_link.append(req)
            linked.append(req_id)
        except Requirement.DoesNotExist:
            missing.append(req_id)
            logger.warning(f"Requirement '{req_id}' not found for flow '{flow.name}'")

    # Atomic replacement of requirements
    flow.requirements.set(requirements_to_link)

    return {'linked': linked, 'missing': missing}


def sync_yaml_flows_to_db(
    flows: list[FlowDef],
    clear_existing: bool = False,
) -> dict[str, str]:
    """Sync YAML-defined flows to database.

    Creates or updates VerificationFlow records from FlowDef objects.
    Links requirements via M2M relationship using external_id lookup.
    Stores source_file metadata in the steps JSONField as a `_metadata` key.

    Args:
        flows: List of FlowDef objects from YAMLFlowParser
        clear_existing: If True, delete existing flows matching the
            names in the provided list before syncing

    Returns:
        Dict mapping flow name to action ('created', 'updated', or 'deleted')
    """
    results = {}
    flow_names = [f.name for f in flows]

    # Clear flows by name if requested
    if clear_existing and flow_names:
        deleted_count, _ = VerificationFlow.objects.filter(
            name__in=flow_names
        ).delete()
        logger.info(f"Cleared {deleted_count} existing flows")
        # Mark all as will be created
        for name in flow_names:
            results[name] = 'deleted'

    all_missing_requirements = []

    for flow_def in flows:
        # Convert step definitions to dicts for JSON storage
        steps_data = [asdict(step) for step in flow_def.steps]

        # Store source_file metadata as first element with _metadata key
        # Requirements are now linked via M2M relationship
        metadata = {
            '_metadata': {
                'source_file': flow_def.source_file,
            }
        }
        steps_with_metadata = [metadata] + steps_data

        flow, created = VerificationFlow.objects.update_or_create(
            name=flow_def.name,
            defaults={
                'display_name': flow_def.display_name,
                'description': flow_def.description,
                'steps': steps_with_metadata,
                'version': flow_def.version,
                'synced_at': timezone.now(),
            }
        )

        # Link requirements via M2M (after flow exists)
        req_result = _sync_flow_requirements(flow, flow_def.requirements)
        if req_result['missing']:
            all_missing_requirements.extend(req_result['missing'])

        action = 'created' if created else 'updated'
        results[flow_def.name] = action
        linked_count = len(req_result['linked'])
        logger.info(
            f"Flow '{flow_def.name}' {action} (v{flow_def.version}, "
            f"{linked_count} requirements linked)"
        )

    # Summary logging for missing requirements
    if all_missing_requirements:
        unique_missing = sorted(set(all_missing_requirements))
        logger.warning(
            f"Missing requirements during sync: {', '.join(unique_missing)}"
        )

    return results
