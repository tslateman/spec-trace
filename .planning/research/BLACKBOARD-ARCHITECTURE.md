# Design: Agent Blackboard Architecture for SpecTrace

**Status:** Proposal
**Author:** Claude + Tim
**Date:** 2026-01-25

## Summary

Extend SpecTrace into an agent coordination platform. AI agents (Planner, Coder, Reviewer) coordinate through SpecTrace's database — claiming tasks, submitting work, recording reviews. No agent-to-agent messages. The database is the blackboard.

## Problem

SpecTrace observes what was built. It does not orchestrate what gets built.

AI agents work fast but break things. They fabricate success, merge bad code, skip tests. The fix: adversarial review where Coder cannot merge own work and Reviewer cannot implement.

This requires coordination. Agents need to claim tasks, submit work, request reviews, record outcomes. SpecTrace already has requirements, validations, and results. Add a task state machine and it becomes a blackboard.

## Why SpecTrace?

| Liza (YAML file) | SpecTrace (database) |
|------------------|---------------------|
| `done_when` in YAML | `InAppValidation.steps` with pass/fail |
| Task specs | `Requirement` with structured fields |
| Review outcome | `InAppValidationResult.status` |
| Sprint boundary | `InAppValidationRun` |
| Audit trail | `InAppValidationResult.context` |

SpecTrace adds: queries, history, dashboard, existing API.

---

## Goals

1. Multi-agent coordination through database and API
2. All agent work traces to requirements
3. Role separation enforced (Coder can't merge own work)
4. Existing dashboard and API unchanged
5. Humans monitor agent activity in real-time

## Non-Goals

1. Running agents — SpecTrace coordinates, not executes
2. Git operations — agents manage their own worktrees
3. LLM orchestration — agents decide; SpecTrace records
4. Replacing validation flow — this extends it

---

## Proposed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SPECTRACE (Blackboard)                       │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Requirements │  │  AgentTasks  │  │   Agents     │              │
│  │  (specs)     │──│  (work items)│──│ (registered) │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                  │                 │                      │
│         │                  ▼                 │                      │
│         │         ┌──────────────┐          │                      │
│         └────────▶│ TaskHistory  │◀─────────┘                      │
│                   │  (audit log) │                                  │
│                   └──────────────┘                                  │
│                                                                      │
│  REST API: /api/agent/*                                             │
│  Dashboard: /admin/agent-tasks/                                     │
└─────────────────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
     ┌────────────┐       ┌────────────┐       ┌────────────┐
     │  Planner   │       │   Coder    │       │  Reviewer  │
     │  Agent     │       │   Agent    │       │   Agent    │
     └────────────┘       └────────────┘       └────────────┘
            │                    │                    │
            └──────────┬─────────┴───────────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  Git Repository  │
              │  (worktrees)     │
              └──────────────────┘
```

### New Models

#### AgentTask

Work item on the blackboard. Agents claim it, implement it, submit for review.

```python
class AgentTaskStatus(models.TextChoices):
    """Task lifecycle states."""
    DRAFT = 'draft', 'Draft'                    # Planner is still defining
    UNCLAIMED = 'unclaimed', 'Unclaimed'        # Ready for a Coder to claim
    CLAIMED = 'claimed', 'Claimed'              # Coder has claimed, not started
    IN_PROGRESS = 'in_progress', 'In Progress'  # Coder is implementing
    READY_FOR_REVIEW = 'ready_for_review', 'Ready for Review'
    CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
    APPROVED = 'approved', 'Approved'           # Reviewer approved
    MERGED = 'merged', 'Merged'                 # Work integrated
    BLOCKED = 'blocked', 'Blocked'              # Waiting on dependency or human
    ABANDONED = 'abandoned', 'Abandoned'        # Task deemed wrong after retries


class AgentTask(models.Model):
    """A unit of work on the blackboard."""

    # Identity
    external_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Task ID (e.g., 'task-auth-login-001')"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Link to requirement(s)
    requirements = models.ManyToManyField(
        Requirement,
        related_name='agent_tasks',
        help_text="Requirements this task implements"
    )

    # State machine
    status = models.CharField(
        max_length=20,
        choices=AgentTaskStatus.choices,
        default=AgentTaskStatus.DRAFT,
        db_index=True,
    )

    # Claiming
    claimed_by = models.ForeignKey(
        'Agent',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='claimed_tasks',
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    lease_expires = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Task returns to UNCLAIMED if lease expires"
    )

    # Git integration
    worktree_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to git worktree (e.g., '.worktrees/task-auth-login-001')"
    )
    branch_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Git branch for this task"
    )
    commit_sha = models.CharField(
        max_length=40,
        blank=True,
        help_text="Latest commit SHA submitted for review"
    )

    # Falsifiable completion criteria (critical!)
    done_when = models.JSONField(
        default=list,
        help_text="List of falsifiable criteria (e.g., 'python -m hello exits 0')"
    )

    # Dependencies
    depends_on = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='blocks',
        help_text="Tasks that must complete before this one"
    )

    # Spec reference
    spec_ref = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to spec file (e.g., 'specs/vision.md')"
    )

    # Scope boundaries (from Liza)
    scope_in = models.JSONField(
        default=list,
        help_text="What IS in scope for this task"
    )
    scope_out = models.JSONField(
        default=list,
        help_text="What is NOT in scope (explicit exclusions)"
    )

    # Retry tracking (for hypothesis exhaustion)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(
        default=2,
        help_text="After this many failures by different coders, task is presumed wrong"
    )

    # Sprint/batch grouping
    sprint = models.ForeignKey(
        'AgentSprint',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Agent Task"
        verbose_name_plural = "Agent Tasks"

    def __str__(self):
        return f"{self.external_id}: {self.title}"

    def is_claimable(self) -> bool:
        """Check if task can be claimed."""
        if self.status != AgentTaskStatus.UNCLAIMED:
            return False
        # Check dependencies
        for dep in self.depends_on.all():
            if dep.status != AgentTaskStatus.MERGED:
                return False
        return True

    def can_transition_to(self, new_status: str) -> bool:
        """Validate state transition."""
        allowed = STATE_TRANSITIONS.get(self.status, [])
        return new_status in allowed


# State machine transitions
STATE_TRANSITIONS = {
    AgentTaskStatus.DRAFT: [AgentTaskStatus.UNCLAIMED, AgentTaskStatus.ABANDONED],
    AgentTaskStatus.UNCLAIMED: [AgentTaskStatus.CLAIMED, AgentTaskStatus.BLOCKED],
    AgentTaskStatus.CLAIMED: [AgentTaskStatus.IN_PROGRESS, AgentTaskStatus.UNCLAIMED],
    AgentTaskStatus.IN_PROGRESS: [AgentTaskStatus.READY_FOR_REVIEW, AgentTaskStatus.BLOCKED],
    AgentTaskStatus.READY_FOR_REVIEW: [AgentTaskStatus.APPROVED, AgentTaskStatus.CHANGES_REQUESTED],
    AgentTaskStatus.CHANGES_REQUESTED: [AgentTaskStatus.READY_FOR_REVIEW, AgentTaskStatus.ABANDONED],
    AgentTaskStatus.APPROVED: [AgentTaskStatus.MERGED],
    AgentTaskStatus.BLOCKED: [AgentTaskStatus.UNCLAIMED, AgentTaskStatus.ABANDONED],
    AgentTaskStatus.MERGED: [],  # Terminal
    AgentTaskStatus.ABANDONED: [],  # Terminal
}
```

#### Agent

Registered agent with role (Planner, Coder, Reviewer). Role determines allowed actions.

```python
class AgentRole(models.TextChoices):
    """Agent specializations."""
    PLANNER = 'planner', 'Planner'
    CODER = 'coder', 'Coder'
    REVIEWER = 'reviewer', 'Code Reviewer'
    SPEC_WRITER = 'spec_writer', 'Spec Writer'
    SPEC_REVIEWER = 'spec_reviewer', 'Spec Reviewer'


class Agent(models.Model):
    """A registered agent that can interact with the blackboard."""

    agent_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique agent identifier (e.g., 'coder-1', 'reviewer-opus')"
    )
    role = models.CharField(
        max_length=20,
        choices=AgentRole.choices,
        db_index=True,
    )

    # Status
    is_active = models.BooleanField(default=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    # Configuration
    config = models.JSONField(
        default=dict,
        help_text="Agent-specific configuration"
    )

    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"

    def __str__(self):
        return f"{self.agent_id} ({self.role})"

    def can_claim_tasks(self) -> bool:
        """Only coders can claim tasks."""
        return self.role == AgentRole.CODER

    def can_review_tasks(self) -> bool:
        """Only reviewers can approve/reject."""
        return self.role == AgentRole.REVIEWER

    def can_create_tasks(self) -> bool:
        """Only planners can create tasks."""
        return self.role == AgentRole.PLANNER
```

#### AgentTaskHistory

Every state change logged. Who did what, when, why.

```python
class AgentTaskHistory(models.Model):
    """Audit trail for task state changes."""

    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name='history',
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # What happened
    action = models.CharField(
        max_length=50,
        help_text="Action taken (e.g., 'CLAIMED', 'SUBMITTED_FOR_REVIEW', 'APPROVED')"
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)

    # Details
    details = models.JSONField(
        default=dict,
        help_text="Additional context (commit SHA, review feedback, etc.)"
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Task History"
        verbose_name_plural = "Task History"

    def __str__(self):
        return f"{self.task.external_id}: {self.action} by {self.agent_id}"
```

#### AgentTaskReview

Review record: decision, done_when verification, feedback, blocking issues.

```python
class ReviewDecision(models.TextChoices):
    APPROVED = 'approved', 'Approved'
    CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
    REJECTED = 'rejected', 'Rejected'  # Task is fundamentally wrong


class AgentTaskReview(models.Model):
    """A review of submitted work."""

    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    reviewer = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
    )

    # Review details
    decision = models.CharField(
        max_length=20,
        choices=ReviewDecision.choices,
    )
    commit_sha = models.CharField(
        max_length=40,
        help_text="The commit SHA that was reviewed"
    )

    # Criteria verification
    done_when_results = models.JSONField(
        default=list,
        help_text="Pass/fail for each done_when criterion"
    )

    # Feedback
    feedback = models.TextField(
        blank=True,
        help_text="Detailed review feedback"
    )
    blocking_issues = models.JSONField(
        default=list,
        help_text="Issues that must be fixed"
    )
    suggestions = models.JSONField(
        default=list,
        help_text="Non-blocking suggestions"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review of {self.task.external_id}: {self.decision}"
```

#### AgentSprint

Batch of related tasks. Tracks progress: total, merged, in-progress, pending.

```python
class AgentSprint(models.Model):
    """A batch of related tasks."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Goal
    goal_description = models.TextField(
        help_text="What this sprint should accomplish"
    )

    # Status
    is_active = models.BooleanField(default=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def progress(self) -> dict:
        """Get sprint progress stats."""
        tasks = self.tasks.all()
        total = tasks.count()
        merged = tasks.filter(status=AgentTaskStatus.MERGED).count()
        in_progress = tasks.filter(
            status__in=[
                AgentTaskStatus.CLAIMED,
                AgentTaskStatus.IN_PROGRESS,
                AgentTaskStatus.READY_FOR_REVIEW,
            ]
        ).count()
        return {
            'total': total,
            'merged': merged,
            'in_progress': in_progress,
            'pending': total - merged - in_progress,
            'percent_complete': round((merged / total) * 100, 1) if total else 0,
        }
```

---

### API Endpoints

New endpoints under `/api/agent/`:

#### Agent Registration

```
POST /api/agent/register/
{
    "agent_id": "coder-1",
    "role": "coder",
    "config": {}
}

Response:
{
    "success": true,
    "agent_id": "coder-1",
    "role": "coder"
}
```

#### Heartbeat

```
POST /api/agent/heartbeat/
{
    "agent_id": "coder-1"
}

Response:
{
    "success": true,
    "timestamp": "2026-01-25T12:00:00Z"
}
```

#### List Claimable Tasks

```
GET /api/agent/tasks/claimable/

Response:
{
    "tasks": [
        {
            "external_id": "task-auth-001",
            "title": "Implement login endpoint",
            "requirements": ["AUTH-01", "AUTH-02"],
            "done_when": [
                "POST /api/auth/login returns 200 with valid credentials",
                "POST /api/auth/login returns 401 with invalid credentials",
                "Tests cover both success and failure cases"
            ],
            "depends_on": [],
            "spec_ref": "specs/auth.md"
        }
    ]
}
```

#### Claim Task

```
POST /api/agent/tasks/claim/
{
    "agent_id": "coder-1",
    "task_id": "task-auth-001",
    "lease_minutes": 30
}

Response:
{
    "success": true,
    "task_id": "task-auth-001",
    "worktree_path": ".worktrees/task-auth-001",
    "branch_name": "work/task-auth-001",
    "lease_expires": "2026-01-25T12:30:00Z"
}
```

#### Update Task Status

```
POST /api/agent/tasks/update/
{
    "agent_id": "coder-1",
    "task_id": "task-auth-001",
    "status": "ready_for_review",
    "commit_sha": "abc123def456...",
    "details": {
        "files_modified": ["auth/views.py", "auth/tests.py"],
        "tests_passing": true
    }
}

Response:
{
    "success": true,
    "task_id": "task-auth-001",
    "status": "ready_for_review"
}
```

#### List Reviewable Tasks

```
GET /api/agent/tasks/reviewable/

Response:
{
    "tasks": [
        {
            "external_id": "task-auth-001",
            "title": "Implement login endpoint",
            "commit_sha": "abc123def456...",
            "submitted_by": "coder-1",
            "submitted_at": "2026-01-25T12:15:00Z",
            "done_when": [...],
            "spec_ref": "specs/auth.md"
        }
    ]
}
```

#### Submit Review

```
POST /api/agent/tasks/review/
{
    "agent_id": "reviewer-1",
    "task_id": "task-auth-001",
    "commit_sha": "abc123def456...",  # Must match to prevent stale reviews
    "decision": "approved",
    "done_when_results": [
        {"criterion": "POST /api/auth/login returns 200...", "passed": true},
        {"criterion": "POST /api/auth/login returns 401...", "passed": true},
        {"criterion": "Tests cover both...", "passed": true}
    ],
    "feedback": "Clean implementation. All criteria verified.",
    "blocking_issues": [],
    "suggestions": ["Consider adding rate limiting in future"]
}

Response:
{
    "success": true,
    "task_id": "task-auth-001",
    "status": "approved"
}
```

#### Create Tasks (Planner only)

```
POST /api/agent/tasks/create/
{
    "agent_id": "planner-1",
    "sprint_id": 1,
    "tasks": [
        {
            "external_id": "task-auth-001",
            "title": "Implement login endpoint",
            "requirements": ["AUTH-01", "AUTH-02"],
            "done_when": [...],
            "spec_ref": "specs/auth.md",
            "scope_in": ["Login endpoint", "JWT token generation"],
            "scope_out": ["Password reset", "OAuth providers"]
        }
    ]
}

Response:
{
    "success": true,
    "created": 1,
    "task_ids": ["task-auth-001"]
}
```

---

### Dashboard Views

| View | URL | Shows |
|------|-----|-------|
| Task List | `/admin/agent-tasks/` | Filter by status/sprint/agent. Quick actions. |
| Task Detail | `/admin/agent-tasks/<id>/` | done_when criteria, history, reviews, git diff link |
| Agents | `/admin/agents/` | Heartbeats, current tasks, activity log |
| Sprints | `/admin/sprints/` | Progress bars, blocked tasks highlighted |

---

### Role Enforcement

Role separation is enforced at the API level. Coders claim. Reviewers approve. No exceptions.

```python
# In API views

def claim_task(request, data):
    agent = get_object_or_404(Agent, agent_id=data.agent_id)

    # Enforce: only coders can claim
    if not agent.can_claim_tasks():
        return JsonResponse({
            'success': False,
            'error': f'Agent {agent.agent_id} has role {agent.role}, cannot claim tasks'
        }, status=403)

    # ... rest of claim logic


def submit_review(request, data):
    agent = get_object_or_404(Agent, agent_id=data.agent_id)
    task = get_object_or_404(AgentTask, external_id=data.task_id)

    # Enforce: only reviewers can review
    if not agent.can_review_tasks():
        return JsonResponse({
            'success': False,
            'error': f'Agent {agent.agent_id} has role {agent.role}, cannot review'
        }, status=403)

    # Enforce: can't review own work
    if task.claimed_by and task.claimed_by.agent_id == agent.agent_id:
        return JsonResponse({
            'success': False,
            'error': 'Cannot review your own work'
        }, status=403)

    # ... rest of review logic
```

---

### Integration with Existing Models

#### Linking to Requirements

ManyToMany from AgentTask to Requirement. Dashboard shows: Requirements → Tasks → Reviews.

```python
task = AgentTask.objects.create(
    external_id='task-auth-001',
    title='Implement login endpoint',
)
task.requirements.add(
    Requirement.objects.get(external_id='AUTH-01'),
    Requirement.objects.get(external_id='AUTH-02'),
)
```

#### Linking to Validation Results

On merge, trigger validation for linked requirements:

```python
# After merge
validation_run = InAppValidationRun.objects.create(
    source=f'agent-task:{task.external_id}'
)

# Run validations for linked requirements
for req in task.requirements.all():
    for validation in req.inapp_validations.all():
        # Execute validation and record result
        ...
```

---

### Hypothesis Exhaustion

Two coders fail the same task → task is wrong, not the coders. Auto-block and notify Planner to rescope.

```python
def handle_review_rejection(task, review):
    task.attempt_count += 1

    if task.attempt_count >= task.max_attempts:
        # Task has failed too many times
        task.status = AgentTaskStatus.BLOCKED
        AgentTaskHistory.objects.create(
            task=task,
            action='HYPOTHESIS_EXHAUSTED',
            details={
                'attempts': task.attempt_count,
                'reason': 'Multiple coders failed this task - presumed wrong',
                'reviews': [r.id for r in task.reviews.all()],
            }
        )
        # Notify planner to rescope
        notify_planner_to_rescope(task)
    else:
        # Return to unclaimed for another coder to try
        task.status = AgentTaskStatus.UNCLAIMED
        task.claimed_by = None
        task.commit_sha = ''

    task.save()
```

---

### Lease Management

Tasks have expiring leases. Agent crashes → lease expires → task returns to UNCLAIMED.

```python
# Periodic task (celery or cron)
def expire_stale_leases():
    now = timezone.now()
    stale_tasks = AgentTask.objects.filter(
        status=AgentTaskStatus.CLAIMED,
        lease_expires__lt=now,
    )

    for task in stale_tasks:
        AgentTaskHistory.objects.create(
            task=task,
            action='LEASE_EXPIRED',
            from_status=task.status,
            to_status=AgentTaskStatus.UNCLAIMED,
            details={'expired_at': now.isoformat()},
        )
        task.status = AgentTaskStatus.UNCLAIMED
        task.claimed_by = None
        task.save()
```

---

## Migration Path

| Phase | Deliverable |
|-------|-------------|
| 1. Models | AgentTask, Agent, AgentTaskHistory. Admin views. No API. |
| 2. Read API | List tasks, get detail. Dashboard views. Manual task creation. |
| 3. Write API | Claim, update, review endpoints. Role enforcement. Lease management. |
| 4. Agents | API docs. Reference agent. Real multi-agent test. |

---

## Alternatives Considered

| Option | Why Not |
|--------|---------|
| Reuse InAppValidation | Tracks results, not work-in-progress. Wrong lifecycle. |
| File-based blackboard (YAML) | Creates sync issues. Loses database, API, dashboard benefits. |
| External coordination service | Extra deployment. SpecTrace already deployed. |
| GitHub Issues | No atomic claiming. No role enforcement. No done_when criteria. |

---

## Open Questions

1. **WebSocket vs polling?** Better UX but more complexity.
2. **Worktree management?** SpecTrace provides commands, or agents handle themselves?
3. **Agent auth?** API keys, JWT, or trust-the-network?
4. **Rate limiting?** Prevent runaway loops?
5. **Merge trigger?** SpecTrace merges, or just approves?

---

## Success Criteria

1. Agents coordinate through API, no direct communication
2. Role separation enforced (coder can't approve own work)
3. Every state change logged
4. Humans monitor agents in real-time
5. All work traces to requirements
6. Tasks auto-block after repeated failures

---

## References

- [Adversarial Vibe Coding (Tangi Vass)](https://medium.com/@tangi.vass/i-tried-to-kill-vibe-coding-i-built-adversarial-vibe-coding-without-the-vibes-bc4a63872440)
- [Blackboard Architecture (arXiv)](https://arxiv.org/html/2507.01701v1)
- [Building a Multi-Agent Development Workflow](https://itsgg.com/blog/2026/01/08/building-a-multi-agent-development-workflow/)
- [ccswarm (GitHub)](https://github.com/nwiizo/ccswarm)
- [agent-blackboard (GitHub)](https://github.com/claudioed/agent-blackboard)
