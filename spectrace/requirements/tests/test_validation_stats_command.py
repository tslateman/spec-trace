"""Tests for validation-stats management command."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from requirements.models import AgentTask, IntentValidationResult


@pytest.fixture
def tasks(db):
    """Provide test tasks."""
    t1 = AgentTask.objects.create(external_id="TASK-STAT-1", title="Task 1")
    t2 = AgentTask.objects.create(external_id="TASK-STAT-2", title="Task 2")
    return t1, t2


@pytest.fixture
def populate_results(tasks):
    """Populate intent validation results."""
    t1, t2 = tasks

    # 1 passing
    IntentValidationResult.objects.create(
        task=t1,
        commit_sha="abc1234",
        strategic_score=90,
        opportunity_score=80,
        drift_score=85,
        passed=True,
    )

    # 1 failing
    IntentValidationResult.objects.create(
        task=t2,
        commit_sha="def5678",
        strategic_score=60,
        opportunity_score=70,
        drift_score=65,
        passed=False,
        failure_reasons=["Hardcoded test", "Bad naming convention"],
    )


@pytest.mark.django_db
def test_validation_stats_command_text(populate_results):
    """Test text output of validation stats."""
    out = StringIO()
    call_command("validation_stats", stdout=out)

    output = out.getvalue()

    assert "Intent Validation Stats" in output
    assert "Total Evaluations: 2" in output
    assert "Pass Rate: 50.0%" in output
    assert "Strategic Alignment: 75.0/100" in output
    assert "Hardcoded test" in output


@pytest.mark.django_db
def test_validation_stats_command_json(populate_results):
    """Test JSON output of validation stats."""
    out = StringIO()
    call_command("validation_stats", format="json", stdout=out)

    data = json.loads(out.getvalue())

    assert data["total_evaluations"] == 2
    assert data["passed"] == 1
    assert data["failed"] == 1
    assert data["pass_rate_percentage"] == 50.0
    assert data["average_scores"]["strategic"] == 75.0
    assert len(data["top_failure_reasons"]) > 0


@pytest.mark.django_db
def test_validation_stats_command_empty():
    """Test stats with no data."""
    out = StringIO()
    call_command("validation_stats", stdout=out)

    assert "No validation results found" in out.getvalue()
