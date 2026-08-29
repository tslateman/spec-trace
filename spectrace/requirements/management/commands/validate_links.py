"""
Management command to validate test-requirement links for drift and coverage gaps.
"""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements.models import Requirement

from ...validator import validate_high_risk_requirements, validate_links


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
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--require-coverage",
            nargs="*",
            default=["active"],
            help="Requirement statuses that must have test coverage (default: active)",
        )
        parser.add_argument(
            "--check-high-risk",
            action="store_true",
            help="Also validate high-risk requirements have passing tests",
        )

    def handle(self, *args, **options):
        links_file = Path(options["links_file"])
        strict = options["strict"]
        output_format = options["format"]
        require_coverage = options["require_coverage"]
        check_high_risk = options["check_high_risk"]

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

        # Run high-risk validation if requested
        high_risk_result = None
        if check_high_risk:
            high_risk_result = validate_high_risk_requirements()
            # Merge results
            result.errors.extend(high_risk_result.errors)
            result.warnings.extend(high_risk_result.warnings)

        # Output results
        if output_format == "json":
            self.stdout.write(json.dumps(result.to_dict(), indent=2))
        elif output_format == "md":
            self._output_md(result, links_file, high_risk_result)
        else:
            self._output_text(result, links_file, high_risk_result)

        # Determine exit code
        if result.has_errors:
            sys.exit(1)
        elif strict and result.has_warnings:
            sys.exit(1)

    def _get_titles(self, result):
        """Helper to fetch requirement titles from validation results."""
        req_ids = set()
        for issue in result.errors + result.warnings:
            if ":" in issue.id:
                req_ids.add(issue.id.split(":")[-1])
            else:
                req_ids.add(issue.id)
            if "requirement_id" in issue.details:
                req_ids.add(issue.details["requirement_id"])

        reqs = Requirement.objects.filter(external_id__in=req_ids).values_list(
            "external_id", "title"
        )
        return {r[0]: r[1] for r in reqs}

    def _output_md(self, result, links_file, high_risk_result=None):
        """Output Markdown for PR comments."""
        lines = []
        lines.append("## 🔍 SpecTrace Link Validation")
        lines.append(f"**Validating:** `{links_file}`")
        if high_risk_result:
            lines.append(f"*(Checked {high_risk_result.items_checked} high-risk requirements)*")
        lines.append("")

        titles = self._get_titles(result)

        if result.errors:
            lines.append(f"### ❌ Errors ({len(result.errors)})")
            for error in result.errors:
                req_id = error.id.split(":")[-1] if ":" in error.id else error.id
                title = titles.get(req_id, "")
                title_str = f": {title}" if title else ""

                msg = f"- **{error.id}**{title_str}: {error.message}"
                if error.type == "unknown_requirement" and error.details.get("referenced_by"):
                    tests = error.details["referenced_by"]
                    if len(tests) == 1:
                        msg += f" (in `{tests[0]}`)"
                    else:
                        msg += f" (in {len(tests)} tests)"
                elif error.type in ("high_risk_failing_tests", "pr_impacts_failing_high_risk"):
                    failing = error.details.get("failing_tests", [])
                    if failing:
                        msg += f" ({len(failing)} failing)"
                lines.append(msg)
            lines.append("")

        if result.warnings:
            lines.append(f"### ⚠️ Warnings ({len(result.warnings)})")
            for warning in result.warnings:
                req_id = warning.id.split(":")[-1] if ":" in warning.id else warning.id
                title = titles.get(req_id, "")
                title_str = f": {title}" if title else ""
                lines.append(f"- **{warning.id}**{title_str}: {warning.message}")
            lines.append("")

        if not result.errors and not result.warnings:
            lines.append("✅ **No issues found.**")
            lines.append("")

        lines.append("---")
        lines.append(
            f"*Summary: {result.links_checked} links checked, "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings*"
        )

        self.stdout.write("\n".join(lines) + "\n")

    def _output_text(self, result, links_file, high_risk_result=None):
        """Output human-readable validation results."""
        self.stdout.write(
            self.style.SUCCESS(f"🔍 Validating {links_file} against requirements database...\n")
        )

        if high_risk_result:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Also checking {high_risk_result.items_checked} high-risk requirements...\n"
                )
            )

        titles = self._get_titles(result)

        if result.errors:
            self.stdout.write(self.style.ERROR(f"\n❌ ERRORS ({len(result.errors)}):"))
            for error in result.errors:
                req_id = error.id.split(":")[-1] if ":" in error.id else error.id
                title = titles.get(req_id, "")
                title_str = f": {title}" if title else ""

                msg = f"  ✗ {error.id}{title_str}: {error.message}"
                if error.type == "unknown_requirement" and error.details.get("referenced_by"):
                    tests = error.details["referenced_by"]
                    if len(tests) == 1:
                        msg += f" (in {tests[0]})"
                    else:
                        msg += f" (in {len(tests)} tests)"
                elif error.type in (
                    "high_risk_failing_tests",
                    "pr_impacts_failing_high_risk",
                ):
                    failing = error.details.get("failing_tests", [])
                    if failing:
                        msg += f" ({len(failing)} failing)"
                self.stdout.write(self.style.ERROR(msg))

        if result.warnings:
            self.stdout.write(self.style.WARNING(f"\n⚠️ WARNINGS ({len(result.warnings)}):"))
            for warning in result.warnings:
                req_id = warning.id.split(":")[-1] if ":" in warning.id else warning.id
                title = titles.get(req_id, "")
                title_str = f": {title}" if title else ""
                msg = f"  ⚠ {warning.id}{title_str}: {warning.message}"
                self.stdout.write(self.style.WARNING(msg))

        if not result.errors and not result.warnings:
            self.stdout.write(self.style.SUCCESS("\n✅ No issues found."))

        # Summary
        self.stdout.write(
            f"\nSummary: {result.links_checked} links checked, "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings"
        )
