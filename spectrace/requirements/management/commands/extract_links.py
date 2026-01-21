"""Django management command for extracting test-requirement links."""
import json
import sys
from pathlib import Path

import pytest
from django.core.management.base import BaseCommand

from requirements.models import Requirement


class RequirementCollector:
    """Pytest plugin that collects requirement markers from tests."""

    def __init__(self):
        self.links = []

    def pytest_collection_modifyitems(self, items):
        """Collect requirement markers from all test items."""
        for item in items:
            for marker in item.iter_markers(name="requirement"):
                # Each req_id in marker.args becomes a separate link
                for req_id in marker.args:
                    # Extract test metadata
                    test_file = str(Path(item.fspath).relative_to(Path.cwd()))
                    test_function = item.originalname or item.name
                    test_class = item.cls.__name__ if item.cls else None

                    # Get line number from item location
                    line_number = item.location[1] + 1 if item.location else None

                    self.links.append({
                        "test_nodeid": item.nodeid,
                        "requirement_id": req_id,
                        "reason": marker.kwargs.get("reason"),
                        "test_file": test_file,
                        "test_function": test_function,
                        "test_class": test_class,
                        "line_number": line_number,
                    })


class Command(BaseCommand):
    """Extract test-requirement links from pytest markers."""

    help = 'Extract test-requirement links from @pytest.mark.requirement markers'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output file path (defaults to stdout)'
        )
        parser.add_argument(
            '--path',
            type=str,
            default='tests',
            help='Path to test directory or file (default: tests)'
        )
        # Note: Django BaseCommand uses -v/--verbosity, so we just use --verbose
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show verbose output with each mapping'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        collector = RequirementCollector()

        # Build pytest args for collection-only mode
        pytest_args = [
            "--collect-only",
            "-p", "no:terminal",
            "-q",
            options["path"],
        ]

        # Run pytest with our collector plugin
        # Suppress output by redirecting stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = sys.stderr = open('/dev/null', 'w')
            pytest.main(pytest_args, plugins=[collector])
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        # Build summary
        unique_tests = set(link["test_nodeid"] for link in collector.links)
        unique_requirements = set(link["requirement_id"] for link in collector.links)

        output = {
            "version": "1.0",
            "links": collector.links,
            "summary": {
                "total_links": len(collector.links),
                "unique_tests": len(unique_tests),
                "unique_requirements": len(unique_requirements),
            }
        }

        # Validate requirement IDs against database
        if collector.links:
            existing_ids = set(
                Requirement.objects.filter(
                    external_id__in=unique_requirements
                ).values_list('external_id', flat=True)
            )
            unknown_ids = unique_requirements - existing_ids
            if unknown_ids:
                for req_id in sorted(unknown_ids):
                    self.stderr.write(
                        self.style.WARNING(f"Warning: Unknown requirement ID: {req_id}")
                    )

        # Verbose output
        if options["verbose"]:
            for link in collector.links:
                self.stderr.write(
                    f"  {link['test_nodeid']} -> {link['requirement_id']}"
                )

        # Output JSON
        json_output = json.dumps(output, indent=2)
        if options["output"]:
            output_path = Path(options["output"])
            output_path.write_text(json_output)
            self.stderr.write(
                self.style.SUCCESS(f"Written to {output_path}")
            )
        else:
            self.stdout.write(json_output)
