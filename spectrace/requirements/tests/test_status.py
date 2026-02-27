"""Tests for verification status computation."""

import pytest

from requirements.models import (
    Requirement,
    SLOStatus,
    TestResult,
    TestRun,
    VerificationMethod,
)
from requirements.status import (
    compute_unified_verification_status,
    compute_verification_status,
    update_all_verification_statuses,
)


@pytest.fixture
def requirement(db):
    """Create a basic requirement."""
    return Requirement.add_root(
        external_id="REQ-001",
        title="Test Requirement",
        status="active",
        source_file="test.md",
        verification_method=VerificationMethod.TEST,
    )


@pytest.fixture
def test_run(db):
    """Create a test run."""
    return TestRun.objects.create(source_file="results.xml")


class TestComputeVerificationStatus:
    """Tests for basic verification status computation."""

    @pytest.mark.django_db
    def test_compute__untested_when_no_results(self, requirement):
        """Returns 'untested' when requirement has no test results."""
        status = compute_verification_status(requirement)
        assert status == "untested"

    @pytest.mark.django_db
    def test_compute__passing_when_all_pass(self, requirement, test_run):
        """Returns 'passing' when all linked tests pass."""
        result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="passed",
        )
        result.requirements.add(requirement)

        status = compute_verification_status(requirement, test_run)
        assert status == "passing"

    @pytest.mark.django_db
    def test_compute__failing_when_any_fail(self, requirement, test_run):
        """Returns 'failing' when any linked test fails."""
        pass_result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="passed",
        )
        fail_result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_two",
            name="test_two",
            status="failed",
        )
        pass_result.requirements.add(requirement)
        fail_result.requirements.add(requirement)

        status = compute_verification_status(requirement, test_run)
        assert status == "failing"

    @pytest.mark.django_db
    def test_compute__untested_when_all_skipped(self, requirement, test_run):
        """Returns 'untested' when all linked tests are skipped."""
        result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="skipped",
        )
        result.requirements.add(requirement)

        status = compute_verification_status(requirement, test_run)
        assert status == "untested"


class TestComputeUnifiedVerificationStatus:
    """Tests for unified verification status with SLO override."""

    @pytest.mark.django_db
    def test_unified__breached_slo_overrides_to_failing(self, requirement, test_run):
        """INV-B: Breached SLO forces failing status regardless of tests."""
        # Create passing test
        result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="passed",
        )
        result.requirements.add(requirement)

        # Set SLO to breached
        requirement.slo_status = SLOStatus.BREACHED
        requirement.save()

        status = compute_unified_verification_status(requirement, test_run)
        assert status == "failing"

    @pytest.mark.django_db
    def test_unified__met_slo_does_not_override(self, requirement, test_run):
        """Met SLO doesn't change test-based status."""
        result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="passed",
        )
        result.requirements.add(requirement)

        requirement.slo_status = SLOStatus.MET
        requirement.save()

        status = compute_unified_verification_status(requirement, test_run)
        assert status == "passing"


class TestUpdateAllVerificationStatuses:
    """Tests for bulk status update function.

    These tests verify the INV-B bug fix - update_all_verification_statuses
    must use unified logic that honors SLO status.
    """

    @pytest.mark.django_db
    def test_update_all__honors_slo_status(self, requirement, test_run):
        """REGRESSION TEST: update_all_verification_statuses honors SLO status.

        This test verifies the fix for INV-B violation where
        update_all_verification_statuses previously ignored SLO status.
        """
        # Create passing test
        result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="passed",
        )
        result.requirements.add(requirement)

        # Set SLO to breached
        requirement.slo_status = SLOStatus.BREACHED
        requirement.verification_status = "untested"  # Start with non-failing
        requirement.save()

        # Update all statuses
        counts = update_all_verification_statuses(test_run)

        # Requirement should be failing due to breached SLO
        requirement.refresh_from_db()
        assert requirement.verification_status == "failing", (
            "INV-B violated: update_all_verification_statuses must set "
            "breached SLO requirements to failing status"
        )
        assert counts["failing"] >= 1

    @pytest.mark.django_db
    def test_update_all__returns_counts(self, requirement, test_run):
        """Returns dict with counts by status."""
        counts = update_all_verification_statuses(test_run)

        assert "passing" in counts
        assert "failing" in counts
        assert "untested" in counts
        assert sum(counts.values()) == Requirement.objects.count()

    @pytest.mark.django_db
    def test_update_all__respects_latest_run(self, requirement, test_run):
        """Only considers results from specified test run."""
        # Create old run with passing result
        old_run = TestRun.objects.create(source_file="old.xml")
        old_result = TestResult.objects.create(
            test_run=old_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="passed",
        )
        old_result.requirements.add(requirement)

        # Create new run with failing result
        new_result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="failed",
        )
        new_result.requirements.add(requirement)

        # Update using new run
        update_all_verification_statuses(test_run)

        requirement.refresh_from_db()
        assert requirement.verification_status == "failing"
