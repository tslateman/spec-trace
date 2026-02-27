"""Tests for impact_analysis management command."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.services.impact_analyzer import ImpactResult


class TestImpactAnalysisCommand:
    """Tests for impact_analysis management command."""

    def test_command__outputs_json(self, db):
        """Command outputs valid JSON with --format json."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001"],
            affected_tests=["tests/test_foo.py::test_bar"],
            hierarchy_expansion={},
            dependency_expansion={},
            risk_score=0.03,
            risk_level="low",
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            out = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command("impact_analysis", "main", "feature", "--format", "json", stdout=out)

            # Exit 1 because tests affected
            assert exc_info.value.code == 1

            output = json.loads(out.getvalue())
            assert output["changed_requirements"] == ["REQ-001"]
            assert output["affected_tests"] == ["tests/test_foo.py::test_bar"]
            assert output["summary"]["has_impact"] is True
            assert output["risk_score"] == 0.03
            assert output["risk_level"] == "low"

    def test_command__outputs_text(self, db):
        """Command outputs human-readable text by default."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001", "REQ-002"],
            affected_tests=["tests/test_foo.py::test_bar"],
            hierarchy_expansion={"REQ-001": ["REQ-001-A"]},
            dependency_expansion={},
            risk_score=0.14,
            risk_level="low",
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
            assert "Risk: LOW (0.14)" in output

    def test_command__exit_0_no_impact(self, db):
        """Command exits 0 when no tests affected."""
        mock_result = ImpactResult(
            changed_requirements=["REQ-001"],
            affected_tests=[],
            hierarchy_expansion={},
            dependency_expansion={},
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
            dependency_expansion={},
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
            dependency_expansion={},
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
            dependency_expansion={},
        )

        with patch(
            "requirements.management.commands.impact_analysis.ImpactAnalyzer"
        ) as MockAnalyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_result
            MockAnalyzer.return_value = mock_analyzer

            call_command("impact_analysis", "main", "feature", "--spec-dir", "docs/specs")

            MockAnalyzer.assert_called_once_with(spec_dir="docs/specs")
