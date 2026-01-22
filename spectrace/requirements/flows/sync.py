"""Sync code-defined flows to the database.

This module syncs flow definitions from Python code to the database
on startup, making them visible for querying while keeping the code
as the source of truth.
"""

import logging
from dataclasses import asdict

from django.utils import timezone

from requirements.flows.definitions import REGISTERED_FLOWS
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
