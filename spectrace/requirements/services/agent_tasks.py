"""Agent task coordination service for blackboard architecture.

Provides functions for the agent task state machine:
- claim_task: Agent claims an unclaimed task
- start_task: CLAIMED → IN_PROGRESS
- submit_for_review: Submit work for review
- review_task: Approve or request changes
- merge_task: Mark task as merged
- expire_stale_leases: Release tasks with expired leases
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from django.db import transaction
from django.utils import timezone

from requirements.models import (
    AGENT_TASK_STATE_TRANSITIONS,
    Agent,
    AgentTask,
    AgentTaskHistory,
    AgentTaskReview,
    AgentTaskStatus,
)


class TransitionError(Exception):
    """Raised when a state transition is invalid."""

    def __init__(self, message: str, code: str = "TRANSITION_ERROR"):
        super().__init__(message)
        self.code = code


@dataclass
class TransitionResult:
    """Result of a task state transition."""

    success: bool
    task_id: str
    from_status: str
    to_status: str
    message: str
    details: dict | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "task_id": self.task_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "message": self.message,
            **(self.details or {}),
        }


def _log_history(
    task: AgentTask,
    agent: Agent | None,
    action: str,
    from_status: str,
    to_status: str,
    details: dict | None = None,
) -> AgentTaskHistory:
    """Create a history entry for a task action."""
    return AgentTaskHistory.objects.create(
        task=task,
        agent=agent,
        action=action,
        from_status=from_status,
        to_status=to_status,
        details=details or {},
    )


def validate_transition(task: AgentTask, to_status: str, agent: Agent | None = None) -> None:
    """Validate a state transition is allowed.

    Args:
        task: The task to transition
        to_status: Target status
        agent: Agent performing the action (for role checks)

    Raises:
        TransitionError: If transition is invalid
    """
    allowed = AGENT_TASK_STATE_TRANSITIONS.get(task.status, [])

    if to_status not in allowed:
        raise TransitionError(
            f"Cannot transition from '{task.status}' to '{to_status}'. Allowed: {allowed}",
            code="INVALID_TRANSITION",
        )


def get_agent(agent_id: str) -> Agent:
    """Get an agent by ID.

    Args:
        agent_id: Agent identifier

    Returns:
        Agent instance

    Raises:
        TransitionError: If agent not found or inactive
    """
    try:
        agent = Agent.objects.get(agent_id=agent_id)
    except Agent.DoesNotExist:
        raise TransitionError(
            f"Agent '{agent_id}' not found",
            code="AGENT_NOT_FOUND",
        )

    if not agent.is_active:
        raise TransitionError(
            f"Agent '{agent_id}' is inactive",
            code="AGENT_INACTIVE",
        )

    return agent


def get_task(task_id: str) -> AgentTask:
    """Get a task by external ID.

    Args:
        task_id: Task external ID

    Returns:
        AgentTask instance

    Raises:
        TransitionError: If task not found
    """
    try:
        return AgentTask.objects.get(external_id=task_id)
    except AgentTask.DoesNotExist:
        raise TransitionError(
            f"Task '{task_id}' not found",
            code="TASK_NOT_FOUND",
        )


@transaction.atomic
def claim_task(task_id: str, agent_id: str, lease_minutes: int = 30) -> TransitionResult:
    """Claim an unclaimed task for an agent.

    Args:
        task_id: Task external ID
        agent_id: Agent identifier
        lease_minutes: Lease duration (default 30 minutes)

    Returns:
        TransitionResult with outcome

    Raises:
        TransitionError: If task cannot be claimed
    """
    agent = get_agent(agent_id)
    task = get_task(task_id)

    # Role check: only coders can claim tasks
    if not agent.can_claim_tasks():
        raise TransitionError(
            f"Agent '{agent_id}' with role '{agent.role}' cannot claim tasks. "
            f"Only CODER agents can claim tasks.",
            code="ROLE_NOT_ALLOWED",
        )

    # Check agent doesn't already have a claimed task
    current = agent.current_task
    if current and current.external_id != task_id:
        raise TransitionError(
            f"Agent '{agent_id}' already has task '{current.external_id}' in progress",
            code="AGENT_BUSY",
        )

    # Validate transition
    validate_transition(task, AgentTaskStatus.CLAIMED, agent)

    # Check if task is claimable (dependencies met)
    if not task.is_claimable():
        blocked_deps = [
            dep.external_id for dep in task.depends_on.all() if dep.status != AgentTaskStatus.MERGED
        ]
        raise TransitionError(
            f"Task '{task_id}' has unmerged dependencies: {blocked_deps}",
            code="DEPENDENCIES_NOT_MET",
        )

    from_status = task.status
    now = timezone.now()

    # Perform transition
    task.status = AgentTaskStatus.CLAIMED
    task.claimed_by = agent
    task.claimed_at = now
    task.lease_expires = now + timedelta(minutes=lease_minutes)
    task.save()

    # Log history
    _log_history(
        task=task,
        agent=agent,
        action="CLAIMED",
        from_status=from_status,
        to_status=task.status,
        details={"lease_minutes": lease_minutes},
    )

    # Update agent heartbeat
    agent.last_heartbeat = now
    agent.save(update_fields=["last_heartbeat"])

    return TransitionResult(
        success=True,
        task_id=task_id,
        from_status=from_status,
        to_status=task.status,
        message=f"Task claimed by {agent_id}",
        details={
            "lease_expires": task.lease_expires.isoformat(),
            "agent_id": agent_id,
        },
    )


@transaction.atomic
def start_task(task_id: str, agent_id: str) -> TransitionResult:
    """Start work on a claimed task.

    Args:
        task_id: Task external ID
        agent_id: Agent identifier

    Returns:
        TransitionResult with outcome

    Raises:
        TransitionError: If task cannot be started
    """
    agent = get_agent(agent_id)
    task = get_task(task_id)

    # Verify agent owns the task
    if task.claimed_by != agent:
        owner = task.claimed_by.agent_id if task.claimed_by else "no one"
        raise TransitionError(
            f"Task '{task_id}' is claimed by {owner}, not {agent_id}",
            code="NOT_OWNER",
        )

    # Validate transition
    validate_transition(task, AgentTaskStatus.IN_PROGRESS, agent)

    from_status = task.status

    # Perform transition
    task.status = AgentTaskStatus.IN_PROGRESS
    task.save()

    # Log history
    _log_history(
        task=task,
        agent=agent,
        action="STARTED",
        from_status=from_status,
        to_status=task.status,
    )

    return TransitionResult(
        success=True,
        task_id=task_id,
        from_status=from_status,
        to_status=task.status,
        message=f"Task started by {agent_id}",
    )


@transaction.atomic
def submit_for_review(task_id: str, agent_id: str, commit_sha: str) -> TransitionResult:
    """Submit work for review.

    Args:
        task_id: Task external ID
        agent_id: Agent identifier
        commit_sha: Git commit SHA of the submission

    Returns:
        TransitionResult with outcome

    Raises:
        TransitionError: If task cannot be submitted
    """
    agent = get_agent(agent_id)
    task = get_task(task_id)

    # Verify agent owns the task
    if task.claimed_by != agent:
        owner = task.claimed_by.agent_id if task.claimed_by else "no one"
        raise TransitionError(
            f"Task '{task_id}' is claimed by {owner}, not {agent_id}",
            code="NOT_OWNER",
        )

    # Handle CHANGES_REQUESTED → READY_FOR_REVIEW as valid resubmission
    if task.status == AgentTaskStatus.CHANGES_REQUESTED:
        target_status = AgentTaskStatus.READY_FOR_REVIEW
    else:
        target_status = AgentTaskStatus.READY_FOR_REVIEW
        validate_transition(task, target_status, agent)

    from_status = task.status

    # Perform transition
    task.status = target_status
    task.commit_sha = commit_sha
    task.save()

    # Log history
    _log_history(
        task=task,
        agent=agent,
        action="SUBMITTED_FOR_REVIEW",
        from_status=from_status,
        to_status=task.status,
        details={"commit_sha": commit_sha},
    )

    return TransitionResult(
        success=True,
        task_id=task_id,
        from_status=from_status,
        to_status=task.status,
        message=f"Task submitted for review with commit {commit_sha[:7]}",
        details={"commit_sha": commit_sha},
    )


@transaction.atomic
def review_task(
    task_id: str,
    reviewer_id: str,
    decision: Literal["approved", "changes_requested", "rejected"],
    feedback: str = "",
    done_when_results: list[dict] | None = None,
    blocking_issues: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> TransitionResult:
    """Review a submitted task.

    Args:
        task_id: Task external ID
        reviewer_id: Reviewer agent identifier
        decision: Review decision (approved, changes_requested, rejected)
        feedback: Review feedback text
        done_when_results: Results for each done_when criterion
        blocking_issues: Issues that must be fixed
        suggestions: Non-blocking suggestions

    Returns:
        TransitionResult with outcome

    Raises:
        TransitionError: If review cannot be performed
    """
    reviewer = get_agent(reviewer_id)
    task = get_task(task_id)

    # Role check: only reviewers can review
    if not reviewer.can_review_tasks():
        raise TransitionError(
            f"Agent '{reviewer_id}' with role '{reviewer.role}' cannot review tasks. "
            f"Only REVIEWER agents can review.",
            code="ROLE_NOT_ALLOWED",
        )

    # Self-review check: reviewer cannot be the one who did the work
    if task.claimed_by and task.claimed_by.agent_id == reviewer_id:
        raise TransitionError(
            f"Reviewer '{reviewer_id}' cannot review their own work",
            code="SELF_REVIEW_NOT_ALLOWED",
        )

    # Task must be READY_FOR_REVIEW
    if task.status != AgentTaskStatus.READY_FOR_REVIEW:
        raise TransitionError(
            f"Task '{task_id}' is not ready for review (status: {task.status})",
            code="NOT_READY_FOR_REVIEW",
        )

    from_status = task.status

    # Map decision to status
    decision_to_status = {
        "approved": AgentTaskStatus.APPROVED,
        "changes_requested": AgentTaskStatus.CHANGES_REQUESTED,
        "rejected": AgentTaskStatus.ABANDONED,
    }
    to_status = decision_to_status[decision]

    # Validate transition
    validate_transition(task, to_status, reviewer)

    # Create review record
    review = AgentTaskReview.objects.create(
        task=task,
        reviewer=reviewer,
        decision=decision,
        commit_sha=task.commit_sha,
        done_when_results=done_when_results or [],
        feedback=feedback,
        blocking_issues=blocking_issues or [],
        suggestions=suggestions or [],
    )

    # Perform transition
    task.status = to_status
    if decision == "changes_requested":
        task.attempt_count += 1
        # Check hypothesis exhaustion
        if task.attempt_count >= task.max_attempts:
            task.status = AgentTaskStatus.ABANDONED
            to_status = AgentTaskStatus.ABANDONED
    task.save()

    # Log history
    _log_history(
        task=task,
        agent=reviewer,
        action=f"REVIEWED_{decision.upper()}",
        from_status=from_status,
        to_status=task.status,
        details={
            "review_id": review.id,
            "decision": decision,
            "attempt_count": task.attempt_count,
        },
    )

    message = f"Task {decision} by {reviewer_id}"
    if task.status == AgentTaskStatus.ABANDONED and decision == "changes_requested":
        message += f" (abandoned after {task.attempt_count} attempts)"

    return TransitionResult(
        success=True,
        task_id=task_id,
        from_status=from_status,
        to_status=task.status,
        message=message,
        details={
            "decision": decision,
            "review_id": review.id,
            "attempt_count": task.attempt_count,
        },
    )


@transaction.atomic
def merge_task(task_id: str) -> TransitionResult:
    """Mark an approved task as merged.

    Args:
        task_id: Task external ID

    Returns:
        TransitionResult with outcome

    Raises:
        TransitionError: If task cannot be merged
    """
    task = get_task(task_id)

    # Task must be APPROVED
    if task.status != AgentTaskStatus.APPROVED:
        raise TransitionError(
            f"Task '{task_id}' is not approved (status: {task.status})",
            code="NOT_APPROVED",
        )

    from_status = task.status

    # Perform transition
    task.status = AgentTaskStatus.MERGED
    task.save()

    # Log history
    _log_history(
        task=task,
        agent=None,  # System action
        action="MERGED",
        from_status=from_status,
        to_status=task.status,
    )

    return TransitionResult(
        success=True,
        task_id=task_id,
        from_status=from_status,
        to_status=task.status,
        message="Task merged",
    )


@transaction.atomic
def release_task(task_id: str, reason: str = "lease_expired") -> TransitionResult:
    """Release a claimed task back to unclaimed.

    Args:
        task_id: Task external ID
        reason: Reason for release

    Returns:
        TransitionResult with outcome

    Raises:
        TransitionError: If task cannot be released
    """
    task = get_task(task_id)

    # Task must be CLAIMED
    if task.status != AgentTaskStatus.CLAIMED:
        raise TransitionError(
            f"Task '{task_id}' is not claimed (status: {task.status})",
            code="NOT_CLAIMED",
        )

    from_status = task.status
    previous_agent = task.claimed_by

    # Perform transition
    task.status = AgentTaskStatus.UNCLAIMED
    task.claimed_by = None
    task.claimed_at = None
    task.lease_expires = None
    task.save()

    # Log history
    _log_history(
        task=task,
        agent=previous_agent,
        action="RELEASED",
        from_status=from_status,
        to_status=task.status,
        details={"reason": reason},
    )

    return TransitionResult(
        success=True,
        task_id=task_id,
        from_status=from_status,
        to_status=task.status,
        message=f"Task released ({reason})",
        details={"reason": reason},
    )


def expire_stale_leases(dry_run: bool = False) -> list[dict]:
    """Expire tasks with past lease_expires timestamps.

    Args:
        dry_run: If True, report but don't modify

    Returns:
        List of expired task info dicts
    """
    now = timezone.now()
    expired_tasks = AgentTask.objects.filter(
        status=AgentTaskStatus.CLAIMED,
        lease_expires__lt=now,
    ).select_related("claimed_by")

    results = []

    for task in expired_tasks:
        info = {
            "task_id": task.external_id,
            "claimed_by": task.claimed_by.agent_id if task.claimed_by else None,
            "lease_expired_at": task.lease_expires.isoformat() if task.lease_expires else None,
            "released": False,
        }

        if not dry_run:
            try:
                release_task(task.external_id, reason="lease_expired")
                info["released"] = True
            except TransitionError as e:
                info["error"] = str(e)

        results.append(info)

    return results


@transaction.atomic
def register_agent(
    agent_id: str,
    role: Literal["planner", "coder", "reviewer"],
    config: dict | None = None,
) -> Agent:
    """Register a new agent or update existing.

    Args:
        agent_id: Unique agent identifier
        role: Agent role (planner, coder, reviewer)
        config: Optional configuration dict

    Returns:
        Agent instance
    """
    agent, created = Agent.objects.update_or_create(
        agent_id=agent_id,
        defaults={
            "role": role,
            "is_active": True,
            "config": config or {},
            "last_heartbeat": timezone.now(),
        },
    )
    return agent


def list_tasks(
    status: str | None = None,
    sprint_id: int | None = None,
    agent_id: str | None = None,
) -> list[dict]:
    """List tasks with optional filtering.

    Args:
        status: Filter by status
        sprint_id: Filter by sprint
        agent_id: Filter by claimed agent

    Returns:
        List of task dicts
    """
    queryset = AgentTask.objects.select_related("claimed_by", "sprint")

    if status:
        queryset = queryset.filter(status=status)
    if sprint_id:
        queryset = queryset.filter(sprint_id=sprint_id)
    if agent_id:
        queryset = queryset.filter(claimed_by__agent_id=agent_id)

    results = []
    for task in queryset:
        results.append(
            {
                "external_id": task.external_id,
                "title": task.title,
                "status": task.status,
                "claimed_by": task.claimed_by.agent_id if task.claimed_by else None,
                "sprint": task.sprint.name if task.sprint else None,
                "lease_expires": task.lease_expires.isoformat() if task.lease_expires else None,
                "attempt_count": task.attempt_count,
                "created_at": task.created_at.isoformat(),
            }
        )

    return results
