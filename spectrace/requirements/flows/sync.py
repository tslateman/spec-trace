"""Sync code-defined flows to the database.

This module syncs flow definitions from Python code to the database
on startup, making them visible for querying while keeping the code
as the source of truth.

Also supports syncing YAML-defined flows via sync_yaml_flows_to_db().
"""

import logging
from dataclasses import asdict

from django.utils import timezone

from requirements.flows.definitions import REGISTERED_FLOWS, FlowDef
from requirements.models import VerificationFlow

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
        return sync_flows_to_db()
    except Exception as e:
        logger.warning(f"Could not sync flows to database: {e}")
        return None


def sync_yaml_flows_to_db(
    flows: list[FlowDef],
    clear_existing: bool = False,
) -> dict[str, str]:
    """Sync YAML-defined flows to database.

    Creates or updates VerificationFlow records from FlowDef objects.
    Stores metadata (source_file, requirements) in the steps JSONField
    as a `_metadata` key in the first step position.

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

    for flow_def in flows:
        # Convert step definitions to dicts for JSON storage
        steps_data = [asdict(step) for step in flow_def.steps]

        # Store metadata as first element with _metadata key
        # This allows us to store source_file and requirements
        # without schema changes. Phase 23 will add proper M2M linking.
        metadata = {
            '_metadata': {
                'source_file': flow_def.source_file,
                'requirements': flow_def.requirements,
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

        action = 'created' if created else 'updated'
        results[flow_def.name] = action
        logger.info(f"Flow '{flow_def.name}' {action} (v{flow_def.version})")

    return results
