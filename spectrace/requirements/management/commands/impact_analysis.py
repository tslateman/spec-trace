"""
Management command to analyze impact of spec changes on tests.
"""

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from ...services.impact_analyzer import ImpactAnalyzer


class Command(BaseCommand):
    help = "Analyze impact of spec changes on tests between two git refs"

    def add_arguments(self, parser):
        parser.add_argument(
            "base_ref",
            type=str,
            help="Base git ref (commit, branch, tag)",
        )
        parser.add_argument(
            "head_ref",
            type=str,
            help="Head git ref to compare against base",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--include-hierarchy",
            action="store_true",
            default=True,
            help="Include tests from child requirements (default: true)",
        )
        parser.add_argument(
            "--no-hierarchy",
            action="store_true",
            help="Do not include tests from child requirements",
        )
        parser.add_argument(
            "--spec-dir",
            type=str,
            default="specs",
            help="Directory containing spec files (default: specs)",
        )

    def handle(self, *args, **options):
        base_ref = options["base_ref"]
        head_ref = options["head_ref"]
        output_format = options["format"]
        include_hierarchy = not options["no_hierarchy"]
        spec_dir = options["spec_dir"]

        analyzer = ImpactAnalyzer(spec_dir=spec_dir)

        try:
            result = analyzer.analyze(base_ref, head_ref, include_hierarchy=include_hierarchy)
        except ValueError as e:
            raise CommandError(str(e))

        if output_format == "json":
            self._output_json(result)
        else:
            self._output_text(result, base_ref, head_ref)

        # Exit code 1 if tests are affected (for CI gates)
        if result.affected_tests:
            sys.exit(1)

    def _output_json(self, result):
        """Output structured JSON."""
        output = {
            "changed_requirements": result.changed_requirements,
            "affected_tests": result.affected_tests,
            "hierarchy_expansion": result.hierarchy_expansion,
            "summary": {
                "requirements_changed": len(result.changed_requirements),
                "tests_affected": len(result.affected_tests),
                "has_impact": len(result.affected_tests) > 0,
            },
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_text(self, result, base_ref, head_ref):
        """Output human-readable text."""
        self.stdout.write(f"Impact Analysis: {base_ref} → {head_ref}\n")
        self.stdout.write("=" * 50 + "\n")

        if not result.changed_requirements:
            self.stdout.write(self.style.SUCCESS("\nNo spec files changed.\n"))
            return

        # Changed requirements
        self.stdout.write(
            f"\nChanged Requirements ({len(result.changed_requirements)}):\n"
        )
        for req_id in result.changed_requirements:
            self.stdout.write(f"  • {req_id}\n")

        # Hierarchy expansion
        if result.hierarchy_expansion:
            self.stdout.write("\nHierarchy Expansion:\n")
            for parent_id, child_ids in result.hierarchy_expansion.items():
                self.stdout.write(f"  {parent_id} → {', '.join(child_ids)}\n")

        # Affected tests
        if result.affected_tests:
            self.stdout.write(
                self.style.WARNING(
                    f"\nAffected Tests ({len(result.affected_tests)}):\n"
                )
            )
            for test in sorted(result.affected_tests):
                self.stdout.write(f"  ✗ {test}\n")
            self.stdout.write(
                self.style.WARNING(
                    f"\nThese tests should be run to verify the changes.\n"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\nNo tests affected by these changes.\n")
            )
