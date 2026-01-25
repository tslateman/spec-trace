"""Tests for ImpactAnalyzer service."""
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from requirements.models import Requirement, TestRequirementLink
from requirements.services.impact_analyzer import ImpactAnalyzer, ImpactResult


class TestImpactAnalyzerGetChangedFiles:
    """Tests for get_changed_files method."""

    def test_get_changed_files__returns_markdown_files(self, tmp_path):
        """Returns only .md files from git diff."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path, spec_dir="specs")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="specs/auth.md\nspecs/billing.md\nspecs/README.txt\n",
                returncode=0,
            )

            files = analyzer.get_changed_files("main", "feature-branch")

            assert files == ["specs/auth.md", "specs/billing.md"]
            mock_run.assert_called_once()

    def test_get_changed_files__handles_empty_diff(self, tmp_path):
        """Returns empty list when no files changed."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)

            files = analyzer.get_changed_files("main", "main")

            assert files == []

    def test_get_changed_files__raises_on_invalid_ref(self, tmp_path):
        """Raises ValueError for invalid git refs."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git", stderr="fatal: bad revision 'invalid-ref'"
            )

            with pytest.raises(ValueError, match="Git diff failed"):
                analyzer.get_changed_files("invalid-ref", "main")


class TestImpactAnalyzerGetAffectedTests:
    """Tests for get_affected_tests method."""

    def test_get_affected_tests__returns_linked_tests(self, db):
        """Returns tests linked to given requirements."""
        req = Requirement.add_root(
            external_id="REQ-001",
            title="Test Requirement",
            source_file="test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login",
            requirement=req,
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_logout",
            requirement=req,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["REQ-001"])

        assert set(tests) == {
            "tests/test_auth.py::test_login",
            "tests/test_auth.py::test_logout",
        }
        assert hierarchy == {}

    def test_get_affected_tests__includes_hierarchy(self, db):
        """Includes tests from child requirements when hierarchy enabled."""
        parent = Requirement.add_root(
            external_id="REQ-PARENT",
            title="Parent",
            source_file="test.md",
        )
        child = parent.add_child(
            external_id="REQ-CHILD",
            title="Child",
            source_file="test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_child.py::test_feature",
            requirement=child,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["REQ-PARENT"], include_hierarchy=True)

        assert "tests/test_child.py::test_feature" in tests
        assert hierarchy == {"REQ-PARENT": ["REQ-CHILD"]}

    def test_get_affected_tests__skips_hierarchy_when_disabled(self, db):
        """Does not include child tests when hierarchy disabled."""
        parent = Requirement.add_root(
            external_id="REQ-P2",
            title="Parent",
            source_file="test.md",
        )
        child = parent.add_child(
            external_id="REQ-C2",
            title="Child",
            source_file="test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_child.py::test_x",
            requirement=child,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["REQ-P2"], include_hierarchy=False)

        assert tests == []
        assert hierarchy == {}

    def test_get_affected_tests__handles_missing_requirement(self, db):
        """Handles gracefully when requirement doesn't exist."""
        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["NONEXISTENT-REQ"])

        assert tests == []
        assert hierarchy == {}


class TestImpactAnalyzerAnalyze:
    """Tests for full analyze method."""

    def test_analyze__full_flow(self, db, tmp_path):
        """Full analysis returns changed requirements and affected tests."""
        req = Requirement.add_root(
            external_id="REQ-ANALYZE",
            title="Analyze Test",
            source_file="specs/test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_main.py::test_it",
            requirement=req,
        )

        analyzer = ImpactAnalyzer(repo_path=tmp_path, spec_dir="specs")

        with patch.object(analyzer, "get_changed_files", return_value=["specs/test.md"]):
            with patch.object(analyzer, "extract_requirement_ids", return_value=["REQ-ANALYZE"]):
                result = analyzer.analyze("main", "feature")

        assert result.changed_requirements == ["REQ-ANALYZE"]
        assert "tests/test_main.py::test_it" in result.affected_tests

    def test_analyze__no_changes(self, tmp_path):
        """Returns empty result when no spec files changed."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        with patch.object(analyzer, "get_changed_files", return_value=[]):
            result = analyzer.analyze("main", "main")

        assert result.changed_requirements == []
        assert result.affected_tests == []
        assert result.hierarchy_expansion == {}

    def test_analyze__with_hierarchy(self, db, tmp_path):
        """Analysis includes hierarchy expansion."""
        parent = Requirement.add_root(
            external_id="REQ-PARENT-ANALYZE",
            title="Parent",
            source_file="specs/parent.md",
        )
        child = parent.add_child(
            external_id="REQ-CHILD-ANALYZE",
            title="Child",
            source_file="specs/child.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_child.py::test_child_feature",
            requirement=child,
        )

        analyzer = ImpactAnalyzer(repo_path=tmp_path, spec_dir="specs")

        with patch.object(analyzer, "get_changed_files", return_value=["specs/parent.md"]):
            with patch.object(
                analyzer, "extract_requirement_ids", return_value=["REQ-PARENT-ANALYZE"]
            ):
                result = analyzer.analyze("main", "feature", include_hierarchy=True)

        assert "REQ-PARENT-ANALYZE" in result.changed_requirements
        assert "tests/test_child.py::test_child_feature" in result.affected_tests
        assert "REQ-PARENT-ANALYZE" in result.hierarchy_expansion


class TestImpactResult:
    """Tests for ImpactResult dataclass."""

    def test_impact_result__dataclass_creation(self):
        """ImpactResult can be created with all fields."""
        result = ImpactResult(
            changed_requirements=["REQ-001", "REQ-002"],
            affected_tests=["test_a", "test_b"],
            hierarchy_expansion={"REQ-001": ["REQ-001-A"]},
        )

        assert result.changed_requirements == ["REQ-001", "REQ-002"]
        assert result.affected_tests == ["test_a", "test_b"]
        assert result.hierarchy_expansion == {"REQ-001": ["REQ-001-A"]}
