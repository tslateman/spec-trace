"""Tests for validate-intent management command."""

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.models import AgentTask, IntentValidationResult


@pytest.fixture
def task(db):
    """Provide a test agent task."""
    return AgentTask.objects.create(
        external_id="TASK-CMD-1",
        title="Intent Validation Command Test",
    )


@pytest.fixture
def eval_json_path(tmp_path):
    """Provide a path to a test eval JSON file."""
    path = tmp_path / "eval.json"
    data = {
        "strategic_score": 85,
        "opportunity_score": 90,
        "drift_score": 95,
    }
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture
def fail_eval_json_path(tmp_path):
    """Provide a path to a failing test eval JSON file."""
    path = tmp_path / "eval_fail.json"
    data = {
        "strategic_score": 60,
        "opportunity_score": 90,
        "drift_score": 95,
        "failure_reasons": ["Bad architecture"]
    }
    path.write_text(json.dumps(data))
    return str(path)


@pytest.mark.django_db
def test_validate_intent_command_success(task, eval_json_path):
    """Test successful command execution."""
    out = StringIO()
    call_command(
        "validate_intent",
        task.external_id,
        commit_sha="abc1234",
        eval_json=eval_json_path,
        stdout=out,
    )
    
    output = out.getvalue()
    assert "PASSED" in output
    assert "Strategic: 85" in output
    
    # Verify DB record
    result = IntentValidationResult.objects.get(task=task)
    assert result.passed is True
    assert result.strategic_score == 85


@pytest.mark.django_db
def test_validate_intent_command_failure(task, fail_eval_json_path):
    """Test command execution fails and exits when validation fails."""
    out = StringIO()
    
    with pytest.raises(SystemExit) as exc_info:
        call_command(
            "validate_intent",
            task.external_id,
            commit_sha="abc1234",
            eval_json=fail_eval_json_path,
            stdout=out,
        )
        
    assert exc_info.value.code == 1
    
    output = out.getvalue()
    assert "FAILED" in output
    assert "Strategic: 60" in output
    assert "Bad architecture" in output
    
    # Verify DB record
    result = IntentValidationResult.objects.get(task=task)
    assert result.passed is False


@pytest.mark.django_db
def test_validate_intent_command_missing_file(task):
    """Test command fails if JSON file doesn't exist."""
    with pytest.raises(CommandError, match="Evaluation JSON file not found"):
        call_command(
            "validate_intent",
            task.external_id,
            commit_sha="abc1234",
            eval_json="nonexistent.json",
        )
