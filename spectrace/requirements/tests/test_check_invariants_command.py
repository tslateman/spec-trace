"""Tests for check_invariants management command."""

import json
import re
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command, load_command_class

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


class TestCheckInvariantsReadmeDocumentation:
    """The README's description of check_invariants must match its real --check choices."""

    def test_readme_lists_exact_invariant_codes(self):
        """README's check_invariants row must enumerate the exact supported codes."""
        command = load_command_class("requirements", "check_invariants")
        parser = command.create_parser("manage.py", "check_invariants")
        check_action = next(a for a in parser._actions if a.dest == "check")
        actual_codes = sorted(code for code in check_action.choices if code != "all")

        readme_path = Path(__file__).resolve().parents[3] / "README.md"
        readme_line = next(
            line
            for line in readme_path.read_text().splitlines()
            if "check_invariants" in line and "Validate data consistency" in line
        )
        documented_codes = sorted(set(re.findall(r"INV-[A-Z]", readme_line)))

        assert documented_codes == actual_codes, (
            f"README documents {documented_codes} but check_invariants supports {actual_codes}"
        )
