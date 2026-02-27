"""Tests for spec_coverage management command."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from requirements.models import Requirement


@pytest.fixture
def mixed_requirements(db):
    """Create requirements with varied statuses and structure completeness.

    Structure completeness is computed from FRET fields on save:
    scope, condition, component, timing, response (5 fields, each = 0.2).
    """
    reqs = []
    # 2 draft, 0 FRET fields → structure_completeness = 0.0
    for i in range(2):
        reqs.append(
            Requirement.add_root(
                external_id=f"REQ-DRAFT-{i}",
                title=f"Draft {i}",
                status="draft",
                source_file="test.md",
                verification_status="untested",
            )
        )
    # Active, passing, all 5 FRET fields → 1.0
    reqs.append(
        Requirement.add_root(
            external_id="REQ-ACTIVE-0",
            title="Active Passing",
            status="active",
            source_file="test.md",
            verification_status="passing",
            scope="in session",
            condition="always",
            component="auth",
            timing="immediate",
            response="grant access",
        )
    )
    # Active, failing, 3/5 FRET fields → 0.6
    reqs.append(
        Requirement.add_root(
            external_id="REQ-ACTIVE-1",
            title="Active Failing",
            status="active",
            source_file="test.md",
            verification_status="failing",
            scope="global",
            condition="on error",
            component="alerts",
        )
    )
    # Active, passing, 2/5 FRET fields → 0.4
    reqs.append(
        Requirement.add_root(
            external_id="REQ-ACTIVE-2",
            title="Active Passing 2",
            status="active",
            source_file="test.md",
            verification_status="passing",
            scope="dashboard",
            component="ui",
        )
    )
    return reqs


class TestSpecCoverageCommand:
    """Tests for the spec_coverage management command."""

    @pytest.mark.django_db
    def test_handle__no_requirements(self):
        """Zero requirements produces 0% without errors."""
        out = StringIO()
        call_command("spec_coverage", stdout=out)
        output = out.getvalue()
        assert "0.0%" in output

    @pytest.mark.django_db
    def test_handle__text_output(self, mixed_requirements):
        """Text output shows all three metrics with correct values."""
        out = StringIO()
        call_command("spec_coverage", stdout=out)
        output = out.getvalue()
        # spec rate: 3/5 = 60%
        assert "Specification rate: 60.0%" in output
        assert "3/5 non-draft" in output
        # struct rate: avg(0, 0, 1.0, 0.6, 0.4) = 0.4 = 40%
        assert "Structure rate:     40.0%" in output
        # verif rate: 2/5 = 40%
        assert "Verification rate:  40.0%" in output
        assert "2/5 passing" in output

    @pytest.mark.django_db
    def test_handle__json_output(self, mixed_requirements):
        """JSON output has correct schema and values."""
        out = StringIO()
        call_command("spec_coverage", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())

        assert data["specification_rate"] == pytest.approx(0.6)
        assert data["structure_rate"] == pytest.approx(0.4)
        assert data["verification_rate"] == pytest.approx(0.4)
        assert data["counts"]["total"] == 5
        assert data["counts"]["non_draft"] == 3
        assert data["counts"]["passing"] == 2

    @pytest.mark.django_db
    def test_handle__all_passing(self, db):
        """High coverage yields green-level output."""
        for i in range(4):
            Requirement.add_root(
                external_id=f"REQ-PASS-{i}",
                title=f"Passing {i}",
                status="active",
                source_file="test.md",
                verification_status="passing",
                scope="global",
                condition="always",
                component="core",
                timing="immediate",
                # 4/5 fields = 0.8
            )
        out = StringIO()
        call_command("spec_coverage", stdout=out)
        output = out.getvalue()
        assert "100.0%" in output  # spec rate
        assert "80.0%" in output  # struct rate (4/5 fields)

    @pytest.mark.django_db
    def test_handle__json_zero_requirements(self):
        """JSON with no requirements returns zeros without error."""
        out = StringIO()
        call_command("spec_coverage", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())
        assert data["specification_rate"] == 0.0
        assert data["structure_rate"] == 0.0
        assert data["verification_rate"] == 0.0
        assert data["counts"]["total"] == 0
