"""Tests for Lore journal bridge."""

from unittest.mock import patch

import pytest

from requirements.models import (
    Agent,
    AgentRole,
    AgentTask,
    AgentTaskReview,
    AgentTaskStatus,
    ReviewDecision,
)
from requirements.services.agent_tasks import merge_task, review_task
from requirements.services.lore_bridge import (
    _build_decision,
    _build_rationale,
    _format_done_when,
    notify_lore,
)

# =============================================================================
# Unit Tests: formatting helpers
# =============================================================================


class TestFormatDoneWhen:
    def test_empty_results(self):
        assert _format_done_when([]) == "No criteria recorded."

    def test_pass_and_fail(self):
        results = [
            {"criterion": "pytest exits 0", "passed": True},
            {"criterion": "coverage >= 80%", "passed": False, "notes": "got 72%"},
        ]
        formatted = _format_done_when(results)
        assert "[PASS] pytest exits 0" in formatted
        assert "[FAIL] coverage >= 80% -- got 72%" in formatted

    def test_missing_fields(self):
        results = [{"passed": True}]
        assert "[PASS] unknown" in _format_done_when(results)


class TestBuildDecision:
    def test_merged(self):
        assert "merged" in _build_decision("task-001", "Login flow", "MERGED")
        assert "task-001" in _build_decision("task-001", "Login flow", "MERGED")

    def test_abandoned(self):
        assert "abandoned" in _build_decision("task-001", "Login flow", "ABANDONED")


class TestBuildRationale:
    def test_merged_rationale(self):
        rationale = _build_rationale("MERGED", [], 1, 2)
        assert "All done_when criteria passed" in rationale

    def test_abandoned_rationale(self):
        rationale = _build_rationale("ABANDONED", [], 2, 2)
        assert "abandoned after 2/2 attempts" in rationale


# =============================================================================
# Unit Tests: notify_lore
# =============================================================================


class TestNotifyLore:
    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_skips_non_terminal_status(self, mock_path):
        assert notify_lore("t-1", "Task", "IN_PROGRESS") is False

    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_skips_when_lore_missing(self, mock_path):
        mock_path.exists.return_value = False
        assert notify_lore("t-1", "Task", "MERGED") is False

    @patch("requirements.services.lore_bridge.subprocess.run")
    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_calls_lore_on_merge(self, mock_path, mock_run):
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda self: "/dev/lore/lore.sh"
        mock_run.return_value.returncode = 0

        result = notify_lore(
            task_id="task-auth-001",
            task_name="Implement auth",
            status="MERGED",
            done_when_results=[{"criterion": "tests pass", "passed": True}],
            commit_sha="abc123",
        )

        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "journal" in cmd
        assert "record" in cmd
        assert "merged" in cmd[3].lower()

    @patch("requirements.services.lore_bridge.subprocess.run")
    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_calls_lore_on_abandon(self, mock_path, mock_run):
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda self: "/dev/lore/lore.sh"
        mock_run.return_value.returncode = 0

        result = notify_lore(
            task_id="task-auth-001",
            task_name="Implement auth",
            status="ABANDONED",
            attempt_count=2,
            max_attempts=2,
        )

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "abandoned" in cmd[3].lower()

    @patch("requirements.services.lore_bridge.subprocess.run")
    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_fail_open_on_timeout(self, mock_path, mock_run):
        import subprocess

        mock_path.exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="lore", timeout=10)

        result = notify_lore("t-1", "Task", "MERGED")

        assert result is False

    @patch("requirements.services.lore_bridge.subprocess.run")
    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_fail_open_on_nonzero_exit(self, mock_path, mock_run):
        mock_path.exists.return_value = True
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "error"

        result = notify_lore("t-1", "Task", "MERGED")

        assert result is False

    @patch("requirements.services.lore_bridge.subprocess.run")
    @patch("requirements.services.lore_bridge.LORE_SH")
    def test_tags_include_status(self, mock_path, mock_run):
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda self: "/dev/lore/lore.sh"
        mock_run.return_value.returncode = 0

        notify_lore("t-1", "Task", "MERGED")

        cmd = mock_run.call_args[0][0]
        tags_idx = cmd.index("--tags") + 1
        assert "merged" in cmd[tags_idx]
        assert "spec-trace" in cmd[tags_idx]


# =============================================================================
# Integration Tests: merge_task and review_task call notify_lore
# =============================================================================


class TestMergeTaskNotifiesLore:
    @patch("requirements.services.agent_tasks.notify_lore")
    def test_merge_calls_notify_lore(self, mock_notify, db):
        """merge_task writes outcome to Lore."""
        task = AgentTask.objects.create(
            external_id="task-lore-merge",
            title="Lore merge test",
            status=AgentTaskStatus.APPROVED,
            commit_sha="def456",
        )
        reviewer = Agent.objects.create(agent_id="rev-1", role=AgentRole.REVIEWER, is_active=True)
        AgentTaskReview.objects.create(
            task=task,
            reviewer=reviewer,
            decision=ReviewDecision.APPROVED,
            commit_sha="def456",
            done_when_results=[{"criterion": "tests pass", "passed": True}],
        )

        merge_task("task-lore-merge")

        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        assert call_kwargs["task_id"] == "task-lore-merge"
        assert call_kwargs["status"] == "MERGED"
        assert call_kwargs["done_when_results"] == [{"criterion": "tests pass", "passed": True}]
        assert call_kwargs["commit_sha"] == "def456"

    @patch("requirements.services.agent_tasks.notify_lore")
    def test_merge_without_review_passes_none(self, mock_notify, db):
        """merge_task handles missing review gracefully."""
        AgentTask.objects.create(
            external_id="task-no-review",
            title="No review",
            status=AgentTaskStatus.APPROVED,
        )

        merge_task("task-no-review")

        call_kwargs = mock_notify.call_args[1]
        assert call_kwargs["done_when_results"] is None


class TestReviewAbandonNotifiesLore:
    @patch("requirements.services.agent_tasks.notify_lore")
    def test_hypothesis_exhaustion_calls_notify_lore(self, mock_notify, db):
        """Task abandoned via hypothesis exhaustion writes to Lore."""
        coder = Agent.objects.create(agent_id="coder-exhaust", role=AgentRole.CODER, is_active=True)
        reviewer = Agent.objects.create(
            agent_id="reviewer-exhaust", role=AgentRole.REVIEWER, is_active=True
        )
        AgentTask.objects.create(
            external_id="task-exhaust-lore",
            title="Exhaustion test",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder,
            commit_sha="bbb222",
            attempt_count=1,
            max_attempts=2,
        )

        review_task(
            task_id="task-exhaust-lore",
            reviewer_id="reviewer-exhaust",
            decision="changes_requested",
            feedback="Still broken",
        )

        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        assert call_kwargs["status"] == "ABANDONED"
        assert call_kwargs["attempt_count"] == 2

    @patch("requirements.services.agent_tasks.notify_lore")
    def test_approved_review_does_not_notify(self, mock_notify, db):
        """Approved review (non-terminal) does not write to Lore."""
        coder = Agent.objects.create(agent_id="coder-approve", role=AgentRole.CODER, is_active=True)
        reviewer = Agent.objects.create(
            agent_id="reviewer-approve", role=AgentRole.REVIEWER, is_active=True
        )
        AgentTask.objects.create(
            external_id="task-approve",
            title="Approved task",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder,
            commit_sha="ccc333",
        )

        review_task(
            task_id="task-approve",
            reviewer_id="reviewer-approve",
            decision="approved",
        )

        mock_notify.assert_not_called()
