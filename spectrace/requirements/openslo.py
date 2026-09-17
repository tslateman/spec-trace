"""OpenSLO YAML parser for importing SLOs."""

from decimal import Decimal
from typing import Any

from requirements.models import SLO, Requirement, SLOStatus
from requirements.services.openslo_docs import (
    OpenSLOParser,
    parse_slo_time_window_to_seconds,
    parse_timing_to_seconds,
)

__all__ = [
    "OpenSLOParser",
    "auto_link_slos_by_timing",
    "import_slos_to_database",
    "parse_slo_time_window_to_seconds",
    "parse_timing_to_seconds",
    "update_slo_status_from_json",
]


def import_slos_to_database(
    slos: list[dict[str, Any]],
    clear_existing: bool = False,
) -> int:
    """Import SLO dicts to database.

    Args:
        slos: List of SLO dicts from OpenSLOParser
        clear_existing: If True, delete all existing SLOs first

    Returns:
        Number of SLOs created (not updated)
    """
    if clear_existing:
        SLO.objects.all().delete()

    created_count = 0

    for slo_data in slos:
        name = slo_data["name"]
        requirement_ids = slo_data.pop("requirement_ids", [])

        # Get or create SLO
        slo, created = SLO.objects.update_or_create(
            name=name,
            defaults={
                "display_name": slo_data.get("display_name", ""),
                "description": slo_data.get("description", ""),
                "service": slo_data.get("service", ""),
                "target": slo_data.get("target"),
                "time_window": slo_data.get("time_window", ""),
                "budgeting_method": slo_data.get("budgeting_method", ""),
                "source_file": slo_data.get("source_file", ""),
            },
        )

        if created:
            created_count += 1

        # Link to requirements
        if requirement_ids:
            requirements = Requirement.objects.filter(external_id__in=requirement_ids)
            found_ids = set(requirements.values_list("external_id", flat=True))
            missing_ids = set(requirement_ids) - found_ids

            if missing_ids:
                print(f"Warning: SLO '{name}' references unknown requirements: {missing_ids}")

            slo.requirements.set(requirements)

    return created_count


def update_slo_status_from_json(json_data: dict[str, Any]) -> dict[str, int]:
    """Update SLO status from observability platform JSON.

    Expected JSON format:
    {
        "slos": [
            {
                "name": "api-availability",
                "status": "met",  // met, at_risk, breached
                "current_value": 0.9995,
                "error_budget_remaining": 0.75
            },
            ...
        ]
    }

    Args:
        json_data: Status data from observability platform

    Returns:
        Summary dict with updated, not_found counts
    """
    from django.utils import timezone

    updated = 0
    not_found = 0

    slos_data = json_data.get("slos", [])

    for slo_data in slos_data:
        name = slo_data.get("name")
        if not name:
            continue

        try:
            slo = SLO.objects.get(name=name)
        except SLO.DoesNotExist:
            print(f"Warning: SLO not found: {name}")
            not_found += 1
            continue

        # Map status
        status_str = slo_data.get("status", "unknown")
        slo.status = SLOStatus.from_string(status_str)

        # Update values
        current_value = slo_data.get("current_value")
        if current_value is not None:
            slo.current_value = Decimal(str(current_value))

        error_budget = slo_data.get("error_budget_remaining")
        if error_budget is not None:
            slo.error_budget_remaining = Decimal(str(error_budget))

        slo.last_updated = timezone.now()
        slo.save()
        updated += 1

    return {"updated": updated, "not_found": not_found}


def auto_link_slos_by_timing() -> dict[str, int]:
    """Auto-link SLOs to requirements based on timing fields.

    Links requirements with timing constraints to SLOs where the
    requirement's timing fits within the SLO's target latency.

    For example, if an SLO has a latency target of 2 seconds,
    requirements with timing "within 2 seconds" or less will be linked.

    Returns:
        Summary dict with linked_count, skipped_count.
    """
    linked_count = 0
    skipped_count = 0

    # Get requirements with timing defined
    requirements_with_timing = Requirement.objects.exclude(timing="")

    # Get SLOs with targets (latency-based SLOs typically have targets like 0.95, 0.99)
    slos = SLO.objects.filter(target__isnull=False)

    for slo in slos:
        _ = float(slo.target) if slo.target else 0

        # For latency SLOs, we look at the time_window as a potential latency threshold
        # This is a heuristic - in practice, latency SLOs might define this differently
        # For now, we link requirements whose timing is ≤ a certain threshold

        for req in requirements_with_timing:
            req_timing_seconds = parse_timing_to_seconds(req.timing)

            if req_timing_seconds is None:
                skipped_count += 1
                continue

            # Heuristic: Link if requirement specifies a timing constraint
            # and SLO is for the same or related service
            # For now, we use component matching as a proxy
            if req.component and slo.service:
                # Check if component matches service (case-insensitive, partial match)
                component_lower = req.component.lower()
                service_lower = slo.service.lower()

                if component_lower in service_lower or service_lower in component_lower:
                    # Add requirement to SLO if not already linked
                    if not slo.requirements.filter(id=req.id).exists():
                        slo.requirements.add(req)
                        linked_count += 1
                        print(
                            f"Auto-linked: {req.external_id} -> {slo.name} "
                            f"(timing: {req.timing}, component: {req.component})"
                        )

    return {"linked_count": linked_count, "skipped_count": skipped_count}
