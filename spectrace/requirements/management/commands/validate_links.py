"""
Management command to validate test-requirement links for drift and coverage gaps.
"""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...validator import validate_links


class Command(BaseCommand):
    help = "Validate test-requirement links for drift and coverage gaps"

    def add_arguments(self, parser):
        parser.add_argument(
            "links_file",
            type=str,
            help="Path to links.json file",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as errors (exit code 1 on warnings)",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--require-coverage",
            nargs="*",
            default=["active"],
            help="Requirement statuses that must have test coverage (default: active)",
        )

    def handle(self, *args, **options):
        links_file = Path(options["links_file"])
        strict = options["strict"]
        output_format = options["format"]
        require_coverage = options["require_coverage"]

        # Validate links file exists
        if not links_file.exists():
            raise CommandError(f"Links file not found: {links_file}")

        # Parse links file
        try:
            with open(links_file) as f:
                links_data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in links file: {e}")

        # Run validation
        result = validate_links(links_data, require_coverage_for=require_coverage)

        # Output results
        if output_format == "json":
            self.stdout.write(json.dumps(result.to_dict(), indent=2))
        else:
            self._output_text(result, links_file)

        # Determine exit code
        if result.has_errors:
            sys.exit(1)
        elif strict and result.has_warnings:
            sys.exit(1)

    def _output_text(self, result, links_file):
        """Output human-readable validation results."""
        self.stdout.write(f"Validating {links_file} against requirements database...\n")

        if result.errors:
            self.stdout.write(self.style.ERROR(f"\nERRORS ({len(result.errors)}):"))
            for error in result.errors:
                msg = f"  \u2717 {error.id}: {error.message}"
                if error.type == "unknown_requirement" and error.details.get("referenced_by"):
                    tests = error.details["referenced_by"]
                    if len(tests) == 1:
                        msg += f" (in {tests[0]})"
                    else:
                        msg += f" (in {len(tests)} tests)"
                self.stdout.write(self.style.ERROR(msg))

        if result.warnings:
            self.stdout.write(self.style.WARNING(f"\nWARNINGS ({len(result.warnings)}):"))
            for warning in result.warnings:
                msg = f"  \u26a0 {warning.id}: {warning.message}"
                self.stdout.write(self.style.WARNING(msg))

        if not result.errors and not result.warnings:
            self.stdout.write(self.style.SUCCESS("\nNo issues found."))

        # Summary
        self.stdout.write(
            f"\nSummary: {result.links_checked} links checked, "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings"
        )
