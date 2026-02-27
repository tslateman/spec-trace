"""Tests for spectrace Linear integration features."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from requirements.importer import update_test_requirement_links
from requirements.models import (
    ConflictConfidence,
    ConflictLog,
    ConflictPattern,
    Requirement,
    TestRequirementLink,
    TestResult,
    TestRun,
)
from requirements.services.conflict_detector import ConflictDetector, ConflictResult


@pytest.fixture
def sample_requirement(db):
    """Create a single requirement."""
    return Requirement.add_root(
        external_id="CAN-1234",
        title="Test Authentication Flow",
        status="active",
        source_file="linear://TEAM/CAN-1234",
    )


@pytest.fixture
def sample_requirements(db):
    """Create multiple requirements."""
    req1 = Requirement.add_root(
        external_id="CAN-1234",
        title="Authentication Flow",
        status="active",
        source_file="linear://TEAM/CAN-1234",
    )
    req2 = Requirement.add_root(
        external_id="CAN-5678",
        title="User Profile",
        status="active",
        source_file="linear://TEAM/CAN-5678",
    )
    return [req1, req2]


@pytest.fixture
def test_run_with_ci(db):
    """Create a test run with CI metadata."""
    return TestRun.objects.create(
        source_file="test-results.xml",
        git_sha="abc123def456789012345678901234567890abcd",
        git_branch="feature/auth",
        ci_job_url="https://github.com/org/repo/actions/runs/12345",
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )


@pytest.fixture
def test_requirement_link(db, sample_requirement):
    """Create a test-requirement link."""
    return TestRequirementLink.objects.create(
        test_nodeid="tests/test_auth.py::test_login",
        requirement=sample_requirement,
        last_status="unknown",
    )


class TestTestRequirementLinkModel:
    """Tests for TestRequirementLink model."""

    def test_create_link__stores_test_nodeid(self, db, sample_requirement):
        """Link creation stores test nodeid correctly."""
        link = TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login",
            requirement=sample_requirement,
        )
        assert link.test_nodeid == "tests/test_auth.py::test_login"
        assert link.requirement == sample_requirement
        assert link.last_status == "unknown"

    def test_unique_constraint__prevents_duplicate_links(self, db, sample_requirement):
        """Cannot create duplicate links for same test-requirement pair."""
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login",
            requirement=sample_requirement,
        )
        with pytest.raises(Exception):  # IntegrityError
            TestRequirementLink.objects.create(
                test_nodeid="tests/test_auth.py::test_login",
                requirement=sample_requirement,
            )

    def test_str_representation__shows_mapping(self, test_requirement_link):
        """String representation shows test → requirement."""
        assert "test_login" in str(test_requirement_link)
        assert "CAN-1234" in str(test_requirement_link)


class TestConflictLogModel:
    """Tests for ConflictLog model."""

    def test_create_conflict__stores_requirements(self, db, sample_requirements):
        """Conflict creation stores both requirements."""
        req_a, req_b = sample_requirements
        conflict = ConflictLog.objects.create(
            requirement_a=req_a,
            requirement_b=req_b,
            pattern=ConflictPattern.MUTUAL_EXCLUSION,
            confidence=ConflictConfidence.HIGH,
            details={"runs_analyzed": 15},
        )
        assert conflict.requirement_a == req_a
        assert conflict.requirement_b == req_b
        assert conflict.pattern == ConflictPattern.MUTUAL_EXCLUSION
        assert conflict.confidence == ConflictConfidence.HIGH
        assert conflict.resolved is False

    def test_str_representation__shows_conflict(self, db, sample_requirements):
        """String representation shows A ↔ B."""
        req_a, req_b = sample_requirements
        conflict = ConflictLog.objects.create(
            requirement_a=req_a,
            requirement_b=req_b,
            pattern=ConflictPattern.MUTUAL_EXCLUSION,
            confidence=ConflictConfidence.MEDIUM,
        )
        assert "CAN-1234" in str(conflict)
        assert "CAN-5678" in str(conflict)
        assert "Active" in str(conflict)


class TestTestRunCIMetadata:
    """Tests for TestRun CI metadata fields."""

    def test_create_with_ci_metadata__stores_fields(self, test_run_with_ci):
        """Test run stores CI metadata correctly."""
        assert test_run_with_ci.git_sha == "abc123def456789012345678901234567890abcd"
        assert test_run_with_ci.git_branch == "feature/auth"
        assert "github.com" in test_run_with_ci.ci_job_url
        assert test_run_with_ci.started_at is not None
        assert test_run_with_ci.finished_at is not None


class TestImportTestLinksCommand:
    """Tests for import_test_links management command."""

    def test_import_links__creates_link_records(self, db, sample_requirement, tmp_path):
        """Import creates TestRequirementLink records."""
        links_json = tmp_path / "links.json"
        links_json.write_text(
            json.dumps(
                {
                    "collected_at": "2025-01-15T12:00:00Z",
                    "links": [
                        {
                            "test_nodeid": "tests/test_auth.py::test_login",
                            "linear_issue_ids": ["CAN-1234"],
                        }
                    ],
                }
            )
        )

        out = StringIO()
        call_command("import_test_links", str(links_json), stdout=out)

        assert TestRequirementLink.objects.count() == 1
        link = TestRequirementLink.objects.first()
        assert link.test_nodeid == "tests/test_auth.py::test_login"
        assert link.requirement == sample_requirement
        assert link.needs_review is True  # New links flagged for review
        assert "new link" in link.review_reason

    def test_import_links__warns_on_missing_requirement(self, db, tmp_path):
        """Import warns when requirement not found."""
        links_json = tmp_path / "links.json"
        links_json.write_text(
            json.dumps(
                {
                    "links": [
                        {
                            "test_nodeid": "tests/test_auth.py::test_login",
                            "linear_issue_ids": ["MISSING-999"],
                        }
                    ]
                }
            )
        )

        out = StringIO()
        err = StringIO()
        call_command("import_test_links", str(links_json), stdout=out, stderr=err)

        assert TestRequirementLink.objects.count() == 0
        output = out.getvalue()
        assert "MISSING-999" in output

    def test_import_links__updates_existing(
        self, db, sample_requirement, test_requirement_link, tmp_path
    ):
        """Import updates existing links without creating duplicates."""
        links_json = tmp_path / "links.json"
        links_json.write_text(
            json.dumps(
                {
                    "links": [
                        {
                            "test_nodeid": "tests/test_auth.py::test_login",
                            "linear_issue_ids": ["CAN-1234"],
                        }
                    ]
                }
            )
        )

        call_command("import_test_links", str(links_json), stdout=StringIO())

        # Should still be just one link
        assert TestRequirementLink.objects.count() == 1


class TestUpdateTestRequirementLinks:
    """Tests for update_test_requirement_links function."""

    def test_update_links__updates_status_from_results(self, db, sample_requirement):
        """Updates link status from test results."""
        # Create link
        link = TestRequirementLink.objects.create(
            test_nodeid="spectrace/tests/test_auth.py::test_login",
            requirement=sample_requirement,
            last_status="unknown",
        )

        # Create test run with passing result
        test_run = TestRun.objects.create(source_file="results.xml")
        TestResult.objects.create(
            test_run=test_run,
            test_nodeid="spectrace/tests/test_auth.py::test_login",
            name="test_login",
            classname="spectrace.tests.test_auth",
            status="passed",
        )

        # Update links
        summary = update_test_requirement_links(test_run)

        link.refresh_from_db()
        assert link.last_status == "passed"
        assert link.last_run_at == test_run.imported_at
        assert summary["updated_count"] == 1

    def test_update_links__flags_regressions(self, db, sample_requirement):
        """Flags links that regressed from passing to failing."""
        # Create link that was passing
        link = TestRequirementLink.objects.create(
            test_nodeid="spectrace/tests/test_auth.py::test_login",
            requirement=sample_requirement,
            last_status="passed",
            needs_review=False,
        )

        # Create test run with failing result
        test_run = TestRun.objects.create(source_file="results.xml")
        TestResult.objects.create(
            test_run=test_run,
            test_nodeid="spectrace/tests/test_auth.py::test_login",
            name="test_login",
            classname="spectrace.tests.test_auth",
            status="failed",
        )

        # Update links
        summary = update_test_requirement_links(test_run)

        link.refresh_from_db()
        assert link.last_status == "failed"
        assert link.needs_review is True
        assert "status changed" in link.review_reason
        assert len(summary["status_changes"]) == 1


class TestConflictDetector:
    """Tests for ConflictDetector service."""

    def test_detect_mutual_exclusion__returns_empty_with_few_runs(self, db):
        """No conflicts detected with insufficient runs."""
        detector = ConflictDetector(min_runs=10)
        # No runs in database
        conflicts = detector.detect_mutual_exclusion()
        assert conflicts == []

    def test_check_pair__detects_mutual_exclusion_pattern(self, db, sample_requirements):
        """Detects when two requirements never both pass together."""
        req_a, req_b = sample_requirements
        detector = ConflictDetector(min_runs=3, min_overlap=3)

        # Create links for both requirements
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_a.py::test_feature_a",
            requirement=req_a,
            last_status="unknown",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_b.py::test_feature_b",
            requirement=req_b,
            last_status="unknown",
        )

        # Create test runs showing inverse pattern
        # (A passes, B fails) or (A fails, B passes), never both pass
        run_statuses = {}
        for i in range(5):
            run = TestRun.objects.create(source_file=f"run{i}.xml")
            if i % 2 == 0:
                # A passes, B fails
                run_statuses[run.id] = {req_a.id: "passed", req_b.id: "failed"}
            else:
                # A fails, B passes
                run_statuses[run.id] = {req_a.id: "failed", req_b.id: "passed"}

        # Check for mutual exclusion
        conflict = detector._check_pair_for_mutual_exclusion(req_a.id, req_b.id, run_statuses)

        assert conflict is not None
        assert conflict.pattern == ConflictPattern.MUTUAL_EXCLUSION
        assert conflict.requirement_a_external_id == "CAN-1234"
        assert conflict.requirement_b_external_id == "CAN-5678"

    def test_check_pair__no_conflict_when_both_pass(self, db, sample_requirements):
        """No conflict when both requirements can pass together."""
        req_a, req_b = sample_requirements
        detector = ConflictDetector(min_runs=3, min_overlap=3)

        # Create run statuses where both pass at least once
        run_statuses = {
            1: {req_a.id: "passed", req_b.id: "passed"},  # Both pass!
            2: {req_a.id: "passed", req_b.id: "failed"},
            3: {req_a.id: "failed", req_b.id: "passed"},
        }

        conflict = detector._check_pair_for_mutual_exclusion(req_a.id, req_b.id, run_statuses)

        assert conflict is None  # No mutual exclusion

    def test_log_conflicts__creates_records(self, db, sample_requirements):
        """Log conflicts creates ConflictLog records."""
        req_a, req_b = sample_requirements
        detector = ConflictDetector()

        conflict = ConflictResult(
            requirement_a_id=req_a.id,
            requirement_b_id=req_b.id,
            requirement_a_external_id="CAN-1234",
            requirement_b_external_id="CAN-5678",
            pattern=ConflictPattern.MUTUAL_EXCLUSION,
            confidence=ConflictConfidence.HIGH,
            runs_analyzed=15,
            details={"inverse_ratio": 0.9},
        )

        summary = detector.log_conflicts([conflict])

        assert summary["created_count"] == 1
        assert ConflictLog.objects.count() == 1

        logged = ConflictLog.objects.first()
        assert logged.requirement_a == req_a
        assert logged.requirement_b == req_b
        assert logged.confidence == ConflictConfidence.HIGH

    def test_log_conflicts__skips_existing(self, db, sample_requirements):
        """Log conflicts skips already-logged conflicts."""
        req_a, req_b = sample_requirements
        detector = ConflictDetector()

        # Create existing conflict
        ConflictLog.objects.create(
            requirement_a=req_a,
            requirement_b=req_b,
            pattern=ConflictPattern.MUTUAL_EXCLUSION,
            confidence=ConflictConfidence.MEDIUM,
        )

        conflict = ConflictResult(
            requirement_a_id=req_a.id,
            requirement_b_id=req_b.id,
            requirement_a_external_id="CAN-1234",
            requirement_b_external_id="CAN-5678",
            pattern=ConflictPattern.MUTUAL_EXCLUSION,
            confidence=ConflictConfidence.HIGH,
            runs_analyzed=15,
            details={},
        )

        summary = detector.log_conflicts([conflict], skip_existing=True)

        assert summary["created_count"] == 0
        assert summary["skipped_count"] == 1
        assert ConflictLog.objects.count() == 1  # Still just the original
