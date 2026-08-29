"""Tests for intent validation logic."""

import pytest

from requirements.intent_validator import ValidationError, record_validation
from requirements.models import AgentTask


@pytest.fixture
def task(db):
    """Provide a test agent task."""
    return AgentTask.objects.create(
        external_id="TASK-INTENT-1",
        title="Intent Validation Test Task",
        description="Task for testing intent validation",
    )


@pytest.mark.django_db
def test_record_validation_success(task):
    """Test recording a successful validation."""
    eval_data = {
        "strategic_score": 85,
        "opportunity_score": 90,
        "drift_score": 95,
        "failure_reasons": [],
    }

    result = record_validation(task.external_id, "abc1234", eval_data)

    assert result.task == task
    assert result.commit_sha == "abc1234"
    assert result.strategic_score == 85
    assert result.passed is True
    assert len(result.failure_reasons) == 0


@pytest.mark.django_db
def test_record_validation_auto_fail_threshold(task):
    """Test validation automatically fails if a score is below 70."""
    eval_data = {
        "strategic_score": 60,  # Below 70
        "opportunity_score": 90,
        "drift_score": 95,
    }

    result = record_validation(task.external_id, "abc1234", eval_data)
    assert result.passed is False


@pytest.mark.django_db
def test_record_validation_explicit_fail(task):
    """Test validation fails if passed is explicitly false, even with good scores."""
    eval_data = {
        "strategic_score": 90,
        "opportunity_score": 90,
        "drift_score": 90,
        "passed": False,
        "failure_reasons": ["Hardcoded a password"],
    }

    result = record_validation(task.external_id, "abc1234", eval_data)
    assert result.passed is False
    assert "Hardcoded a password" in result.failure_reasons


@pytest.mark.django_db
def test_record_validation_invalid_task():
    """Test validation fails with invalid task ID."""
    eval_data = {
        "strategic_score": 90,
        "opportunity_score": 90,
        "drift_score": 90,
    }

    with pytest.raises(ValidationError, match="Task not found"):
        record_validation("NONEXISTENT", "abc1234", eval_data)
