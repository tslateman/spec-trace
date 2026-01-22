"""OpenSLO YAML parser for importing SLOs."""
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
