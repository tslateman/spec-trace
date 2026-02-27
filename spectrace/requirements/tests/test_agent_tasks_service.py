"""Tests for agent task coordination service."""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from requirements.models import (
    Agent,
    AgentRole,
    AgentSprint,
    AgentTask,
    AgentTaskHistory,
    AgentTaskReview,
    AgentTaskStatus,
    ReviewDecision,
)
from requirements.services.agent_tasks import (
    TransitionError,
    claim_task,
    expire_stale_leases,
    get_agent,
    get_task,
    list_tasks,
    merge_task,
    register_agent,
    release_task,
    review_task,
    start_task,
    submit_for_review,
    validate_transition,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def coder_agent(db):
    """Create a coder agent."""
    return Agent.objects.create(
        agent_id="coder-1",
        role=AgentRole.CODER,
        is_active=True,
    )


@pytest.fixture
def reviewer_agent(db):
    """Create a reviewer agent."""
    return Agent.objects.create(
        agent_id="reviewer-1",
        role=AgentRole.REVIEWER,
        is_active=True,
    )


@pytest.fixture
def planner_agent(db):
    """Create a planner agent."""
    return Agent.objects.create(
        agent_id="planner-1",
        role=AgentRole.PLANNER,
        is_active=True,
    )


@pytest.fixture
def unclaimed_task(db):
    """Create an unclaimed task."""
    return AgentTask.objects.create(
        external_id="task-001",
        title="Implement login",
        status=AgentTaskStatus.UNCLAIMED,
        done_when=["pytest tests/test_login.py exits 0"],
    )


@pytest.fixture
def sprint(db):
    """Create a sprint."""
    return AgentSprint.objects.create(
        name="Sprint 1",
        goal_description="Complete auth flow",
    )


# =============================================================================
# Test: get_agent
# =============================================================================


class TestGetAgent:
    """Tests for get_agent helper."""

    def test_get_agent__returns_agent(self, coder_agent):
        """Returns agent when found."""
        agent = get_agent("coder-1")
        assert agent.agent_id == "coder-1"

    def test_get_agent__raises_on_not_found(self, db):
        """Raises TransitionError when agent not found."""
        with pytest.raises(TransitionError) as exc_info:
            get_agent("nonexistent")
        assert exc_info.value.code == "AGENT_NOT_FOUND"

    def test_get_agent__raises_on_inactive(self, db):
        """Raises TransitionError when agent is inactive."""
        Agent.objects.create(
            agent_id="inactive-agent",
            role=AgentRole.CODER,
            is_active=False,
        )
        with pytest.raises(TransitionError) as exc_info:
            get_agent("inactive-agent")
        assert exc_info.value.code == "AGENT_INACTIVE"


# =============================================================================
# Test: get_task
# =============================================================================


class TestGetTask:
    """Tests for get_task helper."""

    def test_get_task__returns_task(self, unclaimed_task):
        """Returns task when found."""
        task = get_task("task-001")
        assert task.external_id == "task-001"

    def test_get_task__raises_on_not_found(self, db):
        """Raises TransitionError when task not found."""
        with pytest.raises(TransitionError) as exc_info:
            get_task("nonexistent")
        assert exc_info.value.code == "TASK_NOT_FOUND"


# =============================================================================
# Test: validate_transition
# =============================================================================


class TestValidateTransition:
    """Tests for validate_transition."""

    def test_validate_transition__allows_valid(self, unclaimed_task):
        """No error for valid transition."""
        validate_transition(unclaimed_task, AgentTaskStatus.CLAIMED)
        # No exception = success

    def test_validate_transition__rejects_invalid(self, unclaimed_task):
        """Raises TransitionError for invalid transition."""
        with pytest.raises(TransitionError) as exc_info:
            validate_transition(unclaimed_task, AgentTaskStatus.MERGED)
        assert exc_info.value.code == "INVALID_TRANSITION"


# =============================================================================
# Test: claim_task
# =============================================================================


class TestClaimTask:
    """Tests for claim_task."""

    @freeze_time("2025-01-15 12:00:00")
    def test_claim_task__succeeds(self, coder_agent, unclaimed_task):
        """Coder can claim an unclaimed task."""
        result = claim_task("task-001", "coder-1", lease_minutes=30)

        assert result.success
        assert result.from_status == AgentTaskStatus.UNCLAIMED
        assert result.to_status == AgentTaskStatus.CLAIMED
        assert "coder-1" in result.message

        # Verify task state
        unclaimed_task.refresh_from_db()
        assert unclaimed_task.status == AgentTaskStatus.CLAIMED
        assert unclaimed_task.claimed_by == coder_agent
        assert unclaimed_task.lease_expires is not None

        # Verify history
        history = AgentTaskHistory.objects.filter(task=unclaimed_task).first()
        assert history.action == "CLAIMED"
        assert history.agent == coder_agent

    def test_claim_task__rejects_non_coder(self, reviewer_agent, unclaimed_task):
        """Reviewers cannot claim tasks."""
        with pytest.raises(TransitionError) as exc_info:
            claim_task("task-001", "reviewer-1")
        assert exc_info.value.code == "ROLE_NOT_ALLOWED"

    def test_claim_task__rejects_already_claimed(self, coder_agent, db):
        """Cannot claim a task that's already claimed."""
        AgentTask.objects.create(
            external_id="task-002",
            title="Already claimed",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
        )
        Agent.objects.create(
            agent_id="coder-2",
            role=AgentRole.CODER,
            is_active=True,
        )
        with pytest.raises(TransitionError) as exc_info:
            claim_task("task-002", "coder-2")
        assert exc_info.value.code == "INVALID_TRANSITION"

    def test_claim_task__rejects_busy_agent(self, coder_agent, unclaimed_task, db):
        """Agent cannot claim if they already have a task in progress."""
        # Coder already has a task
        AgentTask.objects.create(
            external_id="task-in-progress",
            title="Current task",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=coder_agent,
        )

        with pytest.raises(TransitionError) as exc_info:
            claim_task("task-001", "coder-1")
        assert exc_info.value.code == "AGENT_BUSY"

    def test_claim_task__checks_dependencies(self, coder_agent, db):
        """Cannot claim task with unmerged dependencies."""
        dep_task = AgentTask.objects.create(
            external_id="dep-task",
            title="Dependency",
            status=AgentTaskStatus.IN_PROGRESS,
        )
        task = AgentTask.objects.create(
            external_id="blocked-task",
            title="Blocked",
            status=AgentTaskStatus.UNCLAIMED,
        )
        task.depends_on.add(dep_task)

        with pytest.raises(TransitionError) as exc_info:
            claim_task("blocked-task", "coder-1")
        assert exc_info.value.code == "DEPENDENCIES_NOT_MET"


# =============================================================================
# Test: start_task
# =============================================================================


class TestStartTask:
    """Tests for start_task."""

    def test_start_task__succeeds(self, coder_agent, db):
        """Agent can start their claimed task."""
        task = AgentTask.objects.create(
            external_id="task-start",
            title="Start me",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
        )

        result = start_task("task-start", "coder-1")

        assert result.success
        assert result.to_status == AgentTaskStatus.IN_PROGRESS

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.IN_PROGRESS

    def test_start_task__rejects_non_owner(self, coder_agent, db):
        """Agent cannot start another agent's task."""
        coder2 = Agent.objects.create(
            agent_id="coder-2",
            role=AgentRole.CODER,
            is_active=True,
        )
        AgentTask.objects.create(
            external_id="task-other",
            title="Other task",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder2,
        )

        with pytest.raises(TransitionError) as exc_info:
            start_task("task-other", "coder-1")
        assert exc_info.value.code == "NOT_OWNER"


# =============================================================================
# Test: submit_for_review
# =============================================================================


class TestSubmitForReview:
    """Tests for submit_for_review."""

    def test_submit_for_review__succeeds(self, coder_agent, db):
        """Agent can submit their in-progress task."""
        task = AgentTask.objects.create(
            external_id="task-submit",
            title="Submit me",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=coder_agent,
        )

        result = submit_for_review("task-submit", "coder-1", "abc123def")

        assert result.success
        assert result.to_status == AgentTaskStatus.READY_FOR_REVIEW
        assert "abc123d" in result.message

        task.refresh_from_db()
        assert task.commit_sha == "abc123def"

    def test_submit_for_review__rejects_non_owner(self, coder_agent, db):
        """Agent cannot submit another agent's task."""
        coder2 = Agent.objects.create(
            agent_id="coder-2",
            role=AgentRole.CODER,
            is_active=True,
        )
        AgentTask.objects.create(
            external_id="task-other-submit",
            title="Other task",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=coder2,
        )

        with pytest.raises(TransitionError) as exc_info:
            submit_for_review("task-other-submit", "coder-1", "sha123")
        assert exc_info.value.code == "NOT_OWNER"


# =============================================================================
# Test: review_task
# =============================================================================


class TestReviewTask:
    """Tests for review_task."""

    def test_review_task__approve_succeeds(self, coder_agent, reviewer_agent, db):
        """Reviewer can approve a task."""
        task = AgentTask.objects.create(
            external_id="task-review",
            title="Review me",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder_agent,
            commit_sha="abc123",
        )

        result = review_task(
            task_id="task-review",
            reviewer_id="reviewer-1",
            decision="approved",
            feedback="LGTM",
        )

        assert result.success
        assert result.to_status == AgentTaskStatus.APPROVED

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.APPROVED

        # Verify review record
        review = AgentTaskReview.objects.get(task=task)
        assert review.decision == ReviewDecision.APPROVED
        assert review.feedback == "LGTM"

    def test_review_task__changes_requested(self, coder_agent, reviewer_agent, db):
        """Reviewer can request changes."""
        task = AgentTask.objects.create(
            external_id="task-changes",
            title="Needs changes",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder_agent,
            commit_sha="abc123",
        )

        result = review_task(
            task_id="task-changes",
            reviewer_id="reviewer-1",
            decision="changes_requested",
            feedback="Please fix X",
            blocking_issues=["Issue X"],
        )

        assert result.success
        assert result.to_status == AgentTaskStatus.CHANGES_REQUESTED

        task.refresh_from_db()
        assert task.attempt_count == 1

    def test_review_task__hypothesis_exhaustion(self, coder_agent, reviewer_agent, db):
        """Task abandoned after max attempts."""
        AgentTask.objects.create(
            external_id="task-exhaust",
            title="Exhausted",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder_agent,
            commit_sha="abc123",
            attempt_count=1,
            max_attempts=2,
        )

        result = review_task(
            task_id="task-exhaust",
            reviewer_id="reviewer-1",
            decision="changes_requested",
            feedback="Still broken",
        )

        assert result.success
        assert result.to_status == AgentTaskStatus.ABANDONED
        assert "abandoned" in result.message.lower()

    def test_review_task__rejects_self_review(self, coder_agent, db):
        """Agent cannot review their own work."""
        # Make coder also a reviewer (dual role)
        coder_agent.role = AgentRole.REVIEWER
        coder_agent.save()

        AgentTask.objects.create(
            external_id="task-self",
            title="Self review",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder_agent,
            commit_sha="abc123",
        )

        with pytest.raises(TransitionError) as exc_info:
            review_task("task-self", "coder-1", "approved")
        assert exc_info.value.code == "SELF_REVIEW_NOT_ALLOWED"

    def test_review_task__rejects_non_reviewer(self, coder_agent, db):
        """Non-reviewers cannot review."""
        AgentTask.objects.create(
            external_id="task-nonrev",
            title="No review",
            status=AgentTaskStatus.READY_FOR_REVIEW,
            commit_sha="abc123",
        )
        Agent.objects.create(
            agent_id="coder-2",
            role=AgentRole.CODER,
            is_active=True,
        )

        with pytest.raises(TransitionError) as exc_info:
            review_task("task-nonrev", "coder-2", "approved")
        assert exc_info.value.code == "ROLE_NOT_ALLOWED"


# =============================================================================
# Test: merge_task
# =============================================================================


class TestMergeTask:
    """Tests for merge_task."""

    def test_merge_task__succeeds(self, db):
        """Approved task can be merged."""
        task = AgentTask.objects.create(
            external_id="task-merge",
            title="Merge me",
            status=AgentTaskStatus.APPROVED,
        )

        result = merge_task("task-merge")

        assert result.success
        assert result.to_status == AgentTaskStatus.MERGED

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.MERGED

    def test_merge_task__rejects_unapproved(self, db):
        """Cannot merge unapproved task."""
        AgentTask.objects.create(
            external_id="task-not-approved",
            title="Not approved",
            status=AgentTaskStatus.READY_FOR_REVIEW,
        )

        with pytest.raises(TransitionError) as exc_info:
            merge_task("task-not-approved")
        assert exc_info.value.code == "NOT_APPROVED"


# =============================================================================
# Test: release_task
# =============================================================================


class TestReleaseTask:
    """Tests for release_task."""

    def test_release_task__succeeds(self, coder_agent, db):
        """Claimed task can be released."""
        task = AgentTask.objects.create(
            external_id="task-release",
            title="Release me",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() + timedelta(minutes=30),
        )

        result = release_task("task-release", reason="manual_release")

        assert result.success
        assert result.to_status == AgentTaskStatus.UNCLAIMED

        task.refresh_from_db()
        assert task.claimed_by is None
        assert task.lease_expires is None


# =============================================================================
# Test: expire_stale_leases
# =============================================================================


class TestExpireStaleLeases:
    """Tests for expire_stale_leases."""

    @freeze_time("2025-01-15 12:00:00")
    def test_expire_stale_leases__releases_expired(self, coder_agent, db):
        """Expired leases are released."""
        # Create expired task
        task = AgentTask.objects.create(
            external_id="task-expired",
            title="Expired",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() - timedelta(minutes=5),
        )

        results = expire_stale_leases(dry_run=False)

        assert len(results) == 1
        assert results[0]["task_id"] == "task-expired"
        assert results[0]["released"] is True

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.UNCLAIMED

    @freeze_time("2025-01-15 12:00:00")
    def test_expire_stale_leases__dry_run(self, coder_agent, db):
        """Dry run reports but doesn't modify."""
        task = AgentTask.objects.create(
            external_id="task-expired-dry",
            title="Expired dry",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() - timedelta(minutes=5),
        )

        results = expire_stale_leases(dry_run=True)

        assert len(results) == 1
        assert results[0]["released"] is False

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.CLAIMED  # Unchanged

    @freeze_time("2025-01-15 12:00:00")
    def test_expire_stale_leases__ignores_valid_leases(self, coder_agent, db):
        """Valid leases are not expired."""
        AgentTask.objects.create(
            external_id="task-valid",
            title="Valid",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() + timedelta(minutes=25),
        )

        results = expire_stale_leases(dry_run=False)

        assert len(results) == 0


# =============================================================================
# Test: register_agent
# =============================================================================


class TestRegisterAgent:
    """Tests for register_agent."""

    def test_register_agent__creates_new(self, db):
        """Creates new agent."""
        agent = register_agent("new-coder", "coder", {"model": "claude-3"})

        assert agent.agent_id == "new-coder"
        assert agent.role == AgentRole.CODER
        assert agent.is_active is True
        assert agent.config == {"model": "claude-3"}

    def test_register_agent__updates_existing(self, coder_agent):
        """Updates existing agent."""
        agent = register_agent("coder-1", "reviewer", {"updated": True})

        assert agent.role == AgentRole.REVIEWER
        assert agent.config == {"updated": True}


# =============================================================================
# Test: list_tasks
# =============================================================================


class TestListTasks:
    """Tests for list_tasks."""

    def test_list_tasks__returns_all(self, unclaimed_task, db):
        """Returns all tasks."""
        tasks = list_tasks()

        assert len(tasks) == 1
        assert tasks[0]["external_id"] == "task-001"

    def test_list_tasks__filters_by_status(self, db):
        """Filters by status."""
        AgentTask.objects.create(
            external_id="task-a",
            title="Task A",
            status=AgentTaskStatus.UNCLAIMED,
        )
        AgentTask.objects.create(
            external_id="task-b",
            title="Task B",
            status=AgentTaskStatus.MERGED,
        )

        tasks = list_tasks(status=AgentTaskStatus.UNCLAIMED)

        assert len(tasks) == 1
        assert tasks[0]["external_id"] == "task-a"

    def test_list_tasks__filters_by_sprint(self, sprint, db):
        """Filters by sprint."""
        AgentTask.objects.create(
            external_id="task-sprint",
            title="Sprint task",
            status=AgentTaskStatus.UNCLAIMED,
            sprint=sprint,
        )
        AgentTask.objects.create(
            external_id="task-no-sprint",
            title="No sprint",
            status=AgentTaskStatus.UNCLAIMED,
        )

        tasks = list_tasks(sprint_id=sprint.id)

        assert len(tasks) == 1
        assert tasks[0]["external_id"] == "task-sprint"

    def test_list_tasks__filters_by_agent(self, coder_agent, db):
        """Filters by claimed agent."""
        AgentTask.objects.create(
            external_id="task-claimed",
            title="Claimed",
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
        )
        AgentTask.objects.create(
            external_id="task-other",
            title="Other",
            status=AgentTaskStatus.UNCLAIMED,
        )

        tasks = list_tasks(agent_id="coder-1")

        assert len(tasks) == 1
        assert tasks[0]["external_id"] == "task-claimed"
