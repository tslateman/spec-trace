"""Tests for drift detection logic."""

import pytest

from requirements.models import (
    Requirement,
    TestRequirementLink,
    TestResult,
    TestRun,
)
from requirements.validator import (
    DriftResult,
    detect_all_drift,
    detect_orphan_requirements,
    detect_spec_drift,
    detect_stale_links,
    detect_unmarked_tests,
)


@pytest.fixture
def requirement(db):
    """Create a basic requirement."""
    return Requirement.add_root(
        external_id="REQ-001",
        title="Test Requirement",
        status="active",
        source_file="specs/test.md",
    )


@pytest.fixture
def test_run(db):
    """Create a test run."""
    return TestRun.objects.create(source_file="results.xml")


class TestDetectUnmarkedTests:
    """Tests for unmarked test detection."""

    def test_detect_unmarked__empty_directory(self, tmp_path):
        """No warnings for empty directory."""
        result = detect_unmarked_tests(tmp_path)

        assert not result.has_warnings
        assert result.items_checked == 0

    def test_detect_unmarked__finds_unmarked_test_file(self, tmp_path):
        """Warns about test files without spec markers."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
def test_something():
    assert True
""")

        result = detect_unmarked_tests(tmp_path)

        assert result.has_warnings
        assert len(result.warnings) == 1
        assert result.warnings[0].type == "unmarked_test"

    def test_detect_unmarked__ignores_marked_test_file(self, tmp_path):
        """No warning for test files with spec markers."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
import pytest

@pytest.mark.spec("REQ-001")
def test_something():
    assert True
""")

        result = detect_unmarked_tests(tmp_path)

        assert not result.has_warnings
        assert result.items_checked == 1

    def test_detect_unmarked__recognizes_linear_marker(self, tmp_path):
        """No warning for @pytest.mark.linear marker."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
import pytest

@pytest.mark.linear("CAN-123")
def test_something():
    assert True
""")

        result = detect_unmarked_tests(tmp_path)

        assert not result.has_warnings

    def test_detect_unmarked__ignores_non_test_files(self, tmp_path):
        """Non-test Python files are not checked."""
        helper_file = tmp_path / "conftest.py"
        helper_file.write_text("""
def some_helper():
    pass
""")

        result = detect_unmarked_tests(tmp_path)

        assert result.items_checked == 0

    def test_detect_unmarked__recursive_search(self, tmp_path):
        """Finds test files in subdirectories."""
        subdir = tmp_path / "features"
        subdir.mkdir()
        test_file = subdir / "test_feature.py"
        test_file.write_text("""
def test_feature():
    assert True
""")

        result = detect_unmarked_tests(tmp_path)

        assert result.has_warnings
        assert len(result.warnings) == 1


class TestDetectStaleLinks:
    """Tests for stale link detection."""

    @pytest.mark.django_db
    def test_detect_stale__no_links(self, test_run):
        """No errors when no links exist."""
        result = detect_stale_links()

        assert not result.has_errors

    @pytest.mark.django_db
    def test_detect_stale__finds_stale_link(self, requirement, test_run):
        """Error when link references test not in latest run."""
        # Create a link to a test that doesn't exist in the run
        TestRequirementLink.objects.create(
            test_nodeid="tests/old_test.py::test_deleted",
            requirement=requirement,
            last_status="passed",
        )

        # Add a different test to the run
        TestResult.objects.create(
            test_run=test_run,
            test_nodeid="tests/new_test.py::test_current",
            name="test_current",
            status="passed",
        )

        result = detect_stale_links()

        assert result.has_errors
        assert len(result.errors) == 1
        assert result.errors[0].type == "stale_link"
        assert result.errors[0].details["test_nodeid"] == "tests/old_test.py::test_deleted"

    @pytest.mark.django_db
    def test_detect_stale__link_in_latest_run(self, requirement, test_run):
        """No error when link's test is in latest run."""
        TestRequirementLink.objects.create(
            test_nodeid="tests/test.py::test_one",
            requirement=requirement,
            last_status="passed",
        )
        TestResult.objects.create(
            test_run=test_run,
            test_nodeid="tests/test.py::test_one",
            name="test_one",
            status="passed",
        )

        result = detect_stale_links()

        assert not result.has_errors


class TestDetectOrphanRequirements:
    """Tests for orphan requirement detection."""

    @pytest.mark.django_db
    def test_detect_orphan__warns_for_uncovered_active(self, requirement):
        """Warning for active requirement with no tests or children."""
        result = detect_orphan_requirements()

        assert result.has_warnings
        assert len(result.warnings) == 1
        assert result.warnings[0].type == "orphan_requirement"
        assert result.warnings[0].id == "REQ-001"

    @pytest.mark.django_db
    def test_detect_orphan__no_warning_with_test_link(self, requirement):
        """No warning when requirement has test link."""
        TestRequirementLink.objects.create(
            test_nodeid="tests/test.py::test_one",
            requirement=requirement,
        )

        result = detect_orphan_requirements()

        assert not result.has_warnings

    @pytest.mark.django_db
    def test_detect_orphan__no_warning_for_parent(self, db):
        """No warning for parent requirements (non-leaf)."""
        parent = Requirement.add_root(
            external_id="REQ-PARENT",
            title="Parent Requirement",
            status="active",
            source_file="test.md",
        )
        parent.add_child(
            external_id="REQ-CHILD",
            title="Child Requirement",
            status="active",
            source_file="test.md",
        )

        result = detect_orphan_requirements()

        # Only child should show warning (parent has children)
        orphan_ids = [w.id for w in result.warnings]
        assert "REQ-PARENT" not in orphan_ids
        assert "REQ-CHILD" in orphan_ids

    @pytest.mark.django_db
    def test_detect_orphan__ignores_draft(self, db):
        """No warning for draft requirements."""
        Requirement.add_root(
            external_id="REQ-DRAFT",
            title="Draft Requirement",
            status="draft",
            source_file="test.md",
        )

        result = detect_orphan_requirements()

        orphan_ids = [w.id for w in result.warnings]
        assert "REQ-DRAFT" not in orphan_ids


class TestDetectSpecDrift:
    """Tests for spec file drift detection."""

    @pytest.mark.django_db
    def test_detect_drift__warns_for_modified_spec(self, requirement, test_run, tmp_path):
        """Warning when spec file modified after test run."""
        import os
        import time

        spec_file = tmp_path / "test.md"
        spec_file.write_text("# Requirements\n")

        # Make file appear modified after the test run
        future_time = time.time() + 3600  # 1 hour in the future
        os.utime(spec_file, (future_time, future_time))

        result = detect_spec_drift(tmp_path)

        assert result.has_warnings
        assert len(result.warnings) == 1
        assert result.warnings[0].type == "spec_drift"

    @pytest.mark.django_db
    def test_detect_drift__no_warning_for_unchanged(self, test_run, tmp_path):
        """No warning when spec file older than test run."""
        import os
        import time

        spec_file = tmp_path / "test.md"
        spec_file.write_text("# Requirements\n")

        # Make file appear older than test run
        past_time = time.time() - 3600  # 1 hour in the past
        os.utime(spec_file, (past_time, past_time))

        result = detect_spec_drift(tmp_path)

        assert not result.has_warnings


class TestDetectAllDrift:
    """Tests for combined drift detection."""

    @pytest.mark.django_db
    def test_detect_all__runs_database_checks(self, requirement, test_run):
        """Database checks run even without directory args."""
        result = detect_all_drift()

        # Should at least check orphan requirements
        assert result.items_checked > 0

    @pytest.mark.django_db
    def test_detect_all__includes_file_checks(self, requirement, test_run, tmp_path):
        """File checks run when directories provided."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        result = detect_all_drift(test_dir, specs_dir)

        # Should have run all checks
        assert result.items_checked >= 1  # At least orphan check


class TestDriftResult:
    """Tests for DriftResult dataclass."""

    def test_merge__combines_results(self):
        """Merge combines errors, warnings, and counts."""
        from requirements.validator import ValidationIssue

        result1 = DriftResult(
            errors=[ValidationIssue("a", "id1", "msg1")],
            warnings=[],
            items_checked=5,
        )
        result2 = DriftResult(
            errors=[],
            warnings=[ValidationIssue("b", "id2", "msg2")],
            items_checked=3,
        )

        result1.merge(result2)

        assert len(result1.errors) == 1
        assert len(result1.warnings) == 1
        assert result1.items_checked == 8

    def test_to_dict__serializes_correctly(self):
        """Result converts to JSON-compatible dict."""
        from requirements.validator import ValidationIssue

        result = DriftResult(
            errors=[ValidationIssue("stale_link", "link1", "Stale", {"key": "value"})],
            warnings=[ValidationIssue("orphan", "REQ-001", "Orphan")],
            items_checked=10,
        )

        data = result.to_dict()

        assert data["summary"]["items_checked"] == 10
        assert data["summary"]["errors"] == 1
        assert data["summary"]["warnings"] == 1
        assert data["errors"][0]["type"] == "stale_link"
        assert data["errors"][0]["key"] == "value"
        assert data["warnings"][0]["type"] == "orphan"
