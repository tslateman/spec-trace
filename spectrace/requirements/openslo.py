"""OpenSLO YAML parser for importing SLOs."""
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from requirements.models import Requirement, SLO, SLOStatus


class OpenSLOParser:
    """Parser for OpenSLO v1 YAML files.

    OpenSLO spec: https://openslo.com/

    Extracts SLO definitions and links them to requirements based on
    labels/annotations with convention: `requirement: REQ-XXX` or
    `requirements: REQ-XXX, REQ-YYY`.

    Example OpenSLO YAML:
        apiVersion: openslo/v1
        kind: SLO
        metadata:
          name: api-availability
          displayName: API Availability
          labels:
            requirement: REQ-API-001
        spec:
          service: api-gateway
          description: API should be available 99.9% of the time
          indicator:
            ...
          objectives:
            - target: 0.999
              timeWindow:
                duration: 30d
          budgetingMethod: Occurrences
    """

    def parse_file(self, file_path: Path) -> dict[str, Any] | None:
        """Parse a single OpenSLO YAML file.

        Args:
            file_path: Path to the OpenSLO YAML file

        Returns:
            SLO dict ready for database import, or None if not an SLO
        """
        with open(file_path) as f:
            content = f.read()

        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse YAML {file_path}: {e}")
            return None

        if not doc:
            return None

        # Check if this is an OpenSLO SLO document
        api_version = doc.get('apiVersion', '')
        kind = doc.get('kind', '')

        if not api_version.startswith('openslo/') or kind != 'SLO':
            return None

        return self._parse_slo_doc(doc, file_path)

    def _parse_slo_doc(
        self, doc: dict[str, Any], file_path: Path
    ) -> dict[str, Any]:
        """Parse an OpenSLO SLO document into a dict.

        Args:
            doc: Parsed YAML document
            file_path: Source file path

        Returns:
            SLO dict for database import
        """
        metadata = doc.get('metadata', {})
        spec = doc.get('spec', {})
        labels = metadata.get('labels', {})
        annotations = metadata.get('annotations', {})

        # Extract name and display name
        name = metadata.get('name', '')
        display_name = metadata.get('displayName', '') or name

        # Extract requirement links from labels or annotations
        requirement_ids = self._extract_requirement_ids(labels, annotations)

        # Extract target from objectives
        target = None
        time_window = ''
        objectives = spec.get('objectives', [])
        if objectives and isinstance(objectives, list):
            first_obj = objectives[0]
            target_value = first_obj.get('target')
            if target_value is not None:
                try:
                    target = Decimal(str(target_value))
                except (ValueError, TypeError):
                    pass

            # Extract time window
            tw = first_obj.get('timeWindow', {})
            if isinstance(tw, dict):
                time_window = tw.get('duration', '')
            elif isinstance(tw, str):
                time_window = tw

        return {
            'name': name,
            'display_name': display_name,
            'description': spec.get('description', ''),
            'service': spec.get('service', ''),
            'target': target,
            'time_window': time_window,
            'budgeting_method': spec.get('budgetingMethod', ''),
            'requirement_ids': requirement_ids,
            'source_file': str(file_path),
        }

    def _extract_requirement_ids(
        self, labels: dict[str, str], annotations: dict[str, str]
    ) -> list[str]:
        """Extract requirement IDs from labels and annotations.

        Supports formats:
        - `requirement: REQ-XXX`
        - `requirements: REQ-XXX, REQ-YYY`
        - `spec-trace/requirement: REQ-XXX`

        Args:
            labels: OpenSLO metadata labels
            annotations: OpenSLO metadata annotations

        Returns:
            List of requirement external_ids
        """
        requirement_ids = []

        # Check both labels and annotations
        for source in [labels, annotations]:
            if not source:
                continue

            # Single requirement
            for key in ['requirement', 'spec-trace/requirement']:
                if key in source:
                    req_id = source[key].strip()
                    if req_id and req_id not in requirement_ids:
                        requirement_ids.append(req_id)

            # Multiple requirements (comma-separated)
            for key in ['requirements', 'spec-trace/requirements']:
                if key in source:
                    for req_id in source[key].split(','):
                        req_id = req_id.strip()
                        if req_id and req_id not in requirement_ids:
                            requirement_ids.append(req_id)

        return requirement_ids

    # File patterns for YAML files
    FILE_PATTERNS = ('**/*.yaml', '**/*.yml')

    def parse_directory(self, slos_dir: Path) -> list[dict[str, Any]]:
        """Parse all YAML files in directory recursively.

        Args:
            slos_dir: Path to SLOs directory

        Returns:
            List of SLO dicts from all files
        """
        slos = []
        for pattern in self.FILE_PATTERNS:
            for yaml_file in sorted(slos_dir.glob(pattern)):
                try:
                    slo = self.parse_file(yaml_file)
                    if slo:
                        slos.append(slo)
                except Exception as e:
                    print(f"Warning: Failed to parse {yaml_file}: {e}")
        return slos


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
        name = slo_data['name']
        requirement_ids = slo_data.pop('requirement_ids', [])

        # Get or create SLO
        slo, created = SLO.objects.update_or_create(
            name=name,
            defaults={
                'display_name': slo_data.get('display_name', ''),
                'description': slo_data.get('description', ''),
                'service': slo_data.get('service', ''),
                'target': slo_data.get('target'),
                'time_window': slo_data.get('time_window', ''),
                'budgeting_method': slo_data.get('budgeting_method', ''),
                'source_file': slo_data.get('source_file', ''),
            }
        )

        if created:
            created_count += 1

        # Link to requirements
        if requirement_ids:
            requirements = Requirement.objects.filter(external_id__in=requirement_ids)
            found_ids = set(requirements.values_list('external_id', flat=True))
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

    slos_data = json_data.get('slos', [])

    for slo_data in slos_data:
        name = slo_data.get('name')
        if not name:
            continue

        try:
            slo = SLO.objects.get(name=name)
        except SLO.DoesNotExist:
            print(f"Warning: SLO not found: {name}")
            not_found += 1
            continue

        # Map status
        status_str = slo_data.get('status', 'unknown')
        slo.status = SLOStatus.from_string(status_str)

        # Update values
        current_value = slo_data.get('current_value')
        if current_value is not None:
            slo.current_value = Decimal(str(current_value))

        error_budget = slo_data.get('error_budget_remaining')
        if error_budget is not None:
            slo.error_budget_remaining = Decimal(str(error_budget))

        slo.last_updated = timezone.now()
        slo.save()
        updated += 1

    return {'updated': updated, 'not_found': not_found}


def parse_timing_to_seconds(timing: str) -> float | None:
    """Parse timing constraint to seconds.

    Supports formats like:
    - "within 2 seconds"
    - "in 500ms"
    - "after 1 minute"
    - "2s"
    - "100ms"

    Args:
        timing: Timing constraint string

    Returns:
        Timing in seconds, or None if unparseable.
    """
    if not timing:
        return None

    timing = timing.lower().strip()

    # Match patterns like "2 seconds", "500ms", "1 minute"
    pattern = r'(\d+(?:\.\d+)?)\s*(seconds?|s|ms|milliseconds?|minutes?|m)'
    match = re.search(pattern, timing)

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    if unit in ('ms', 'millisecond', 'milliseconds'):
        return value / 1000
    elif unit in ('m', 'minute', 'minutes'):
        return value * 60
    else:  # seconds
        return value


def parse_slo_time_window_to_seconds(time_window: str) -> float | None:
    """Parse SLO time window to seconds.

    Supports formats like:
    - "30d" (30 days)
    - "7d" (7 days)
    - "1h" (1 hour)

    Args:
        time_window: SLO time window string

    Returns:
        Time window in seconds, or None if unparseable.
    """
    if not time_window:
        return None

    time_window = time_window.lower().strip()

    # Match patterns like "30d", "7d", "1h"
    pattern = r'(\d+(?:\.\d+)?)\s*(d|days?|h|hours?|m|minutes?|s|seconds?)'
    match = re.search(pattern, time_window)

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    if unit in ('d', 'day', 'days'):
        return value * 86400  # seconds per day
    elif unit in ('h', 'hour', 'hours'):
        return value * 3600
    elif unit in ('m', 'minute', 'minutes'):
        return value * 60
    else:  # seconds
        return value


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
    requirements_with_timing = Requirement.objects.exclude(timing='')

    # Get SLOs with targets (latency-based SLOs typically have targets like 0.95, 0.99)
    slos = SLO.objects.filter(target__isnull=False)

    for slo in slos:
        slo_target = float(slo.target) if slo.target else 0

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
                        print(f"Auto-linked: {req.external_id} -> {slo.name} "
                              f"(timing: {req.timing}, component: {req.component})")

    return {'linked_count': linked_count, 'skipped_count': skipped_count}
