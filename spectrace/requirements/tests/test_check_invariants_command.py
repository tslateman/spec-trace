"""Tests for check_invariants management command."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from requirements.models import (
    Requirement,
    SLOStatus,
    TestResult,
    TestRun,
)


@pytest.fixture
def requirement(db):
    """Create a basic requirement."""
    return Requirement.add_root(
        external_id="REQ-001",
        title="Test Requirement",
        status="active",
        source_file="test.md",
        verification_status="passing",
    )


@pytest.fixture
def test_run(db):
    """Create a test run."""
    return TestRun.objects.create(source_file="results.xml")


class TestCheckInvariantsCommand:
    """Tests for the check_invariants management command."""

    @pytest.mark.django_db
    def test_command__runs_all_checks(self, requirement, test_run):
        """Command runs and returns output."""
        out = StringIO()
        # Don't call sys.exit on violations in tests
        try:
            call_command("check_invariants", stdout=out)
        except SystemExit:
            pass  # Expected if violations found

        output = out.getvalue()
        assert "Checking all invariants" in output

    @pytest.mark.django_db
    def test_command__json_format(self, requirement, test_run):
        """Command outputs valid JSON when --format json."""
        out = StringIO()
        try:
            call_command("check_invariants", "--format", "json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)
        assert "violations" in data
        assert "summary" in data

    @pytest.mark.django_db
    def test_command__specific_check(self, requirement, test_run):
        """Command can run specific invariant check."""
        out = StringIO()
        try:
            call_command("check_invariants", "--check", "INV-A", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        assert "INV-A" in output or "No violations" in output

    @pytest.mark.django_db
    def test_command__fix_mode(self, requirement):
        """Command fixes violations when --fix specified."""
        # Create INV-B violation
        requirement.slo_status = SLOStatus.BREACHED
        requirement.verification_status = "passing"
        requirement.save()

        out = StringIO()
        try:
            call_command(
                "check_invariants",
                "--check",
                "INV-B",
                "--fix",
                stdout=out,
            )
        except SystemExit:
            pass

        requirement.refresh_from_db()
        assert requirement.verification_status == "failing"

    @pytest.mark.django_db
    def test_command__exit_code_on_errors(self, requirement, test_run):
        """Command exits with code 1 on errors."""
        # Create status mismatch (INV-A violation)
        result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid="test.py::test_one",
            name="test_one",
            status="failed",
        )
        result.requirements.add(requirement)
        # requirement.verification_status is still 'passing' -> mismatch

        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("check_invariants", "--check", "INV-A", stdout=out)

        assert exc_info.value.code == 1
