---
phase: 13
plan: 01
title: Impact Analysis CLI Command
wave: 1
depends_on: []
files_modified:
  - spectrace/requirements/management/commands/impact_analysis.py (NEW)
  - spectrace/requirements/tests/test_impact_analysis_command.py (NEW)
autonomous: true
---

# Plan 01: Impact Analysis CLI Command

## Goal

Create management command `impact_analysis` for CI pipelines with JSON/text output formats.

## must_haves

- [ ] Command accepts base_ref and head_ref arguments
- [ ] `--format json` outputs structured JSON
- [ ] `--format text` outputs human-readable text (default)
- [ ] `--include-hierarchy` flag to include child requirement tests
- [ ] Exit code 1 when changed requirements affect tests (for CI gates)
- [ ] Exit code 0 when no tests affected

## Tasks

<task id="1">
Create management command at `spectrace/requirements/management/commands/impact_analysis.py`:

```python
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
```
</task>

<task id="2">
Create tests at `spectrace/requirements/tests/test_impact_analysis_command.py`:

```python
"""Tests for impact_analysis management command."""
import json
from io import StringIO
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

import pytest

from requirements.services.impact_analyzer import ImpactResult


class TestImpactAnalysisCommand:
    """Tests for impact_analysis management command."""

    def test_command__outputs_json(self, db):
        """Command outputs valid JSON with --format json."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001"],
            affected_tests=["tests/test_foo.py::test_bar"],
            hierarchy_expansion={},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            out = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "impact_analysis", "main", "feature", "--format", "json", stdout=out
                )

            # Exit 1 because tests affected
            assert exc_info.value.code == 1

            output = json.loads(out.getvalue())
            assert output["changed_requirements"] == ["REQ-001"]
            assert output["affected_tests"] == ["tests/test_foo.py::test_bar"]
            assert output["summary"]["has_impact"] is True

    def test_command__outputs_text(self, db):
        """Command outputs human-readable text by default."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001", "REQ-002"],
            affected_tests=["tests/test_foo.py::test_bar"],
            hierarchy_expansion={"REQ-001": ["REQ-001-A"]},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            out = StringIO()
            with pytest.raises(SystemExit):
                call_command("impact_analysis", "main", "feature", stdout=out)

            output = out.getvalue()
            assert "REQ-001" in output
            assert "REQ-002" in output
            assert "tests/test_foo.py::test_bar" in output
            assert "Hierarchy Expansion" in output

    def test_command__exit_0_no_impact(self, db):
        """Command exits 0 when no tests affected."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001"],
            affected_tests=[],
            hierarchy_expansion={},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            out = StringIO()
            # Should not raise SystemExit with code 1
            call_command("impact_analysis", "main", "feature", stdout=out)

    def test_command__exit_0_no_changes(self, db):
        """Command exits 0 when no spec changes."""
        mock_result = ImpactResult(
            changed_requirements=[],
            affected_tests=[],
            hierarchy_expansion={},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            out = StringIO()
            call_command("impact_analysis", "main", "feature", stdout=out)
            assert "No spec files changed" in out.getvalue()

    def test_command__invalid_ref(self, db):
        """Command raises error for invalid git refs."""
        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.side_effect = ValueError("Git diff failed")
            MockAnalyzer.return_value = mock_analyzer

            with pytest.raises(CommandError, match="Git diff failed"):
                call_command("impact_analysis", "invalid-ref", "main")

    def test_command__no_hierarchy_flag(self, db):
        """Command respects --no-hierarchy flag."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001"],
            affected_tests=[],
            hierarchy_expansion={},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            call_command("impact_analysis", "main", "feature", "--no-hierarchy")

            mock_analyzer.analyze.assert_called_once_with(
                "main", "feature", include_hierarchy=False
            )

    def test_command__spec_dir_option(self, db):
        """Command passes spec_dir to analyzer."""
        mock_result = ImpactResult(
            changed_requirements=[],
            affected_tests=[],
            hierarchy_expansion={},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            call_command(
                "impact_analysis", "main", "feature", "--spec-dir", "docs/specs"
            )

            MockAnalyzer.assert_called_once_with(spec_dir="docs/specs")
```
</task>

<task id="3">
Run tests to verify:

```bash
python -m pytest spectrace/requirements/tests/test_impact_analysis_command.py -v
```
</task>

## Verification

- [ ] `python manage.py impact_analysis main feature` works
- [ ] `--format json` outputs valid JSON
- [ ] Exit code 1 when tests affected
- [ ] Exit code 0 when no tests affected
- [ ] `--no-hierarchy` disables child requirement expansion
