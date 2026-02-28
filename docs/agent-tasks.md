# Agent Task Pipeline

> Coordinate AI agents working on SpecTrace tasks using a blackboard architecture.

## Overview

The agent task pipeline enables multiple AI agents to work on tasks concurrently without conflicts. A **blackboard** (shared database) holds tasks that agents claim, work on, submit for review, and merge.

**Key concepts:**

- **Tasks** move through a state machine from creation to merge
- **Agents** have roles (planner, coder, reviewer) that determine allowed actions
- **Leases** prevent stuck claims from blocking work
- **Invariants** catch data consistency issues

## Quick Start

```bash
# 1. Register agents
python manage.py agent_register coder-1 --role coder
python manage.py agent_register reviewer-1 --role reviewer

# 2. List available tasks
python manage.py agent_tasks --status unclaimed

# 3. Claim and work on a task
python manage.py agent_claim task-001 --agent coder-1
python manage.py agent_start task-001 --agent coder-1
# ... do the work ...
python manage.py agent_submit task-001 --agent coder-1 --commit-sha abc123

# 4. Review and merge
python manage.py agent_review task-001 --reviewer reviewer-1 --decision approved
python manage.py agent_merge task-001
```

## State Machine

Tasks progress through these states:

```
DRAFT → UNCLAIMED → CLAIMED → IN_PROGRESS → READY_FOR_REVIEW → APPROVED → MERGED
                ↑                                    ↓
                └────── CHANGES_REQUESTED ←──────────┘

Terminal states: MERGED, ABANDONED, BLOCKED
```

| State               | Description                             |
| ------------------- | --------------------------------------- |
| `DRAFT`             | Task created but not ready for work     |
| `UNCLAIMED`         | Available for agents to claim           |
| `CLAIMED`           | Agent has claimed with a lease          |
| `IN_PROGRESS`       | Agent is actively working               |
| `READY_FOR_REVIEW`  | Work submitted, awaiting review         |
| `CHANGES_REQUESTED` | Reviewer requested changes              |
| `APPROVED`          | Review passed, ready to merge           |
| `MERGED`            | Work merged (terminal)                  |
| `BLOCKED`           | Waiting on dependencies                 |
| `ABANDONED`         | Hypothesis exhausted after max attempts |

## Agent Roles

| Role       | Can Do                 | Cannot Do       |
| ---------- | ---------------------- | --------------- |
| `planner`  | Create tasks           | Claim or review |
| `coder`    | Claim, start, submit   | Review          |
| `reviewer` | Review, approve/reject | Claim           |

**Self-review is prohibited**: The agent who submitted work cannot review it.

## CLI Commands

### `agent_register`

Register a new agent or update an existing one.

```bash
python manage.py agent_register <agent_id> --role <role> [--config '{"key": "value"}']

# Examples
python manage.py agent_register coder-opus --role coder --config '{"model": "claude-opus-4"}'
python manage.py agent_register reviewer-1 --role reviewer
```

### `agent_tasks`

List tasks with optional filtering.

```bash
python manage.py agent_tasks [--status STATUS] [--sprint ID] [--agent ID] [--format json]

# Examples
python manage.py agent_tasks                           # All tasks
python manage.py agent_tasks --status unclaimed        # Available work
python manage.py agent_tasks --agent coder-1           # My tasks
python manage.py agent_tasks --format json             # JSON for scripts
```

### `agent_claim`

Claim an unclaimed task. Creates a lease (default 30 minutes).

```bash
python manage.py agent_claim <task_id> --agent <agent_id> [--lease-minutes 30]

# Example
python manage.py agent_claim task-auth-001 --agent coder-1 --lease-minutes 60
```

**Errors:**

- `ROLE_NOT_ALLOWED`: Only coders can claim
- `AGENT_BUSY`: Agent already has a task in progress
- `DEPENDENCIES_NOT_MET`: Blocking tasks not merged

### `agent_start`

Begin work on a claimed task.

```bash
python manage.py agent_start <task_id> --agent <agent_id>
```

### `agent_submit`

Submit work for review with a commit SHA.

```bash
python manage.py agent_submit <task_id> --agent <agent_id> --commit-sha <sha>

# Example
python manage.py agent_submit task-auth-001 --agent coder-1 --commit-sha a1b2c3d4e5f6
```

### `agent_review`

Review submitted work. Requires `reviewer` role.

```bash
python manage.py agent_review <task_id> --reviewer <agent_id> --decision <decision> \
    [--feedback "text"] [--blocking-issues "issue1" "issue2"] [--suggestions "idea1"]

# Examples
python manage.py agent_review task-auth-001 --reviewer reviewer-1 --decision approved --feedback "LGTM"

python manage.py agent_review task-auth-001 --reviewer reviewer-1 --decision changes_requested \
    --feedback "Tests missing" --blocking-issues "Add unit tests for edge cases"
```

**Decisions:**

- `approved` → Task moves to APPROVED
- `changes_requested` → Task moves to CHANGES_REQUESTED (can resubmit)
- `rejected` → Task moves to ABANDONED

### `agent_merge`

Mark an approved task as merged.

```bash
python manage.py agent_merge <task_id>
```

### `agent_context`

Assemble a context bundle for an agent task. Bundles task details, linked
specs (with tree hierarchy, test results, FRET fields), drift detection, and
optional Lore overlay into a single artifact.

```bash
python manage.py agent_context <task_id> [--format text|json] [--output <path>]
```

**CLI shortcut:** `st tasks context <task_id>`

**Options:**

| Flag       | Default | Description                                  |
| ---------- | ------- | -------------------------------------------- |
| `--format` | `text`  | Output format: `text` (markdown) or `json`   |
| `--output` | —       | Write output to file (in addition to stdout) |

**Lore integration:** When the Lore CLI is available (`LORE_CLI` env var or
`lore` on `PATH`), the bundle includes a Lore Context section with decisions,
patterns, and failures matching the linked specs' tags and titles. If Lore is
unavailable, the command succeeds with a warning on stderr and omits the
section. Lore subprocess has a 30-second timeout.

**Examples:**

```bash
# Markdown bundle to stdout
python manage.py agent_context TASK-001

# JSON output
python manage.py agent_context TASK-001 --format json

# Write to file for agent handoff
python manage.py agent_context TASK-001 --output /tmp/context.md

# Via CLI
st tasks context TASK-001 --output /tmp/context.md
```

**Bundle contents (markdown format):**

```
# Agent Context Bundle

## Task: {title}
- ID, Status, Done When, Scope In/Out

## Linked Specs
### Spec: {title}
- ID, Status, Priority, Tags, Source, FRET fields
- Description body

#### Tree Hierarchy
- Parent and children (treebeard)

#### Test Results
- Full test nodeid + status list

## Drift
- Stale links and orphan requirements (when issues found)

## Lore Context (Optional)
- Decisions, patterns, failures from Lore
```

### `expire_leases`

Release tasks with expired leases. Run via cron.

```bash
python manage.py expire_leases [--dry-run] [--format json]

# Dry run first
python manage.py expire_leases --dry-run

# Cron entry (every 5 minutes)
*/5 * * * * cd /path/to/spectrace && python manage.py expire_leases
```

## Leases and Timeouts

When an agent claims a task, a **lease** is created with an expiration time (default 30 minutes). This prevents abandoned claims from blocking work.

If the lease expires:

- The `expire_leases` command releases the task back to UNCLAIMED
- Another agent can claim it
- History records the release with reason `lease_expired`

**Best practice**: Set lease duration based on expected task complexity:

- Simple fixes: 15-30 minutes
- Features: 60 minutes
- Complex refactors: 120 minutes

## Hypothesis Exhaustion

Tasks have a `max_attempts` (default 2). After that many `changes_requested` reviews, the task is automatically ABANDONED.

This prevents infinite loops when a task's hypothesis is wrong. If an agent can't solve it after 2 attempts, the task likely needs human review or a different approach.

## Invariants

The system maintains 5 agent-related invariants, checked via `check_invariants`:

| Code  | Rule                                                 |
| ----- | ---------------------------------------------------- |
| INV-G | CLAIMED/IN_PROGRESS tasks have `claimed_by` set      |
| INV-H | CLAIMED tasks have `lease_expires` set               |
| INV-I | Non-DRAFT tasks have at least one history entry      |
| INV-J | APPROVED/MERGED tasks have an approved review record |
| INV-K | Reviewers cannot review their own work               |

```bash
# Check all invariants
python manage.py check_invariants

# Check specific invariant
python manage.py check_invariants --check INV-K

# JSON output for CI
python manage.py check_invariants --format json
```

## JSON Output

All commands support `--format json` for CI/script integration:

```bash
# Claim task and parse result
result=$(python manage.py agent_claim task-001 --agent coder-1 --format json)
success=$(echo "$result" | jq -r '.success')
lease_expires=$(echo "$result" | jq -r '.lease_expires')
```

**Successful claim:**

```json
{
  "success": true,
  "task_id": "task-001",
  "from_status": "unclaimed",
  "to_status": "claimed",
  "message": "Task claimed by coder-1",
  "lease_expires": "2025-01-15T12:30:00Z",
  "agent_id": "coder-1"
}
```

**Failed claim:**

```json
{
  "success": false,
  "error": "Agent 'coder-1' already has task 'task-002' in progress",
  "code": "AGENT_BUSY"
}
```

## Typical Workflow

### Coder Agent

```bash
#!/bin/bash
AGENT_ID="coder-1"

# 1. Find available work
task=$(python manage.py agent_tasks --status unclaimed --format json | jq -r '.tasks[0].external_id')

# 2. Claim it
python manage.py agent_claim "$task" --agent "$AGENT_ID"

# 3. Start work
python manage.py agent_start "$task" --agent "$AGENT_ID"

# 4. Do the work (git operations, code changes, etc.)
# ...

# 5. Submit for review
commit_sha=$(git rev-parse HEAD)
python manage.py agent_submit "$task" --agent "$AGENT_ID" --commit-sha "$commit_sha"
```

### Reviewer Agent

```bash
#!/bin/bash
AGENT_ID="reviewer-1"

# 1. Find tasks ready for review
task=$(python manage.py agent_tasks --status ready_for_review --format json | jq -r '.tasks[0].external_id')

# 2. Review the code (automated checks, etc.)
# ...

# 3. Approve or request changes
python manage.py agent_review "$task" --reviewer "$AGENT_ID" --decision approved
```

### Cron Setup

```bash
# /etc/cron.d/spectrace-leases
*/5 * * * * spectrace cd /path/to/spectrace && python manage.py expire_leases >> /var/log/spectrace-leases.log 2>&1
```

## Error Codes

| Code                      | Meaning                            |
| ------------------------- | ---------------------------------- |
| `AGENT_NOT_FOUND`         | Agent ID doesn't exist             |
| `AGENT_INACTIVE`          | Agent is deactivated               |
| `TASK_NOT_FOUND`          | Task ID doesn't exist              |
| `INVALID_TRANSITION`      | State change not allowed           |
| `ROLE_NOT_ALLOWED`        | Agent role cannot perform action   |
| `AGENT_BUSY`              | Agent already has active task      |
| `DEPENDENCIES_NOT_MET`    | Blocking tasks not merged          |
| `NOT_OWNER`               | Agent doesn't own this task        |
| `NOT_READY_FOR_REVIEW`    | Task not in READY_FOR_REVIEW state |
| `NOT_APPROVED`            | Task not in APPROVED state         |
| `SELF_REVIEW_NOT_ALLOWED` | Cannot review own work             |

## Database Schema

```
AgentTask
├── external_id (unique)
├── title, description
├── status (state machine)
├── claimed_by → Agent
├── claimed_at, lease_expires
├── commit_sha
├── done_when (JSON list of criteria)
├── depends_on (M2M self-referential)
└── sprint → AgentSprint

Agent
├── agent_id (unique)
├── role (planner/coder/reviewer)
├── is_active
└── config (JSON)

AgentTaskHistory
├── task → AgentTask
├── agent → Agent (nullable for system actions)
├── action, from_status, to_status
├── timestamp
└── details (JSON)

AgentTaskReview
├── task → AgentTask
├── reviewer → Agent
├── decision (approved/changes_requested/rejected)
├── commit_sha
├── done_when_results (JSON)
├── feedback, blocking_issues, suggestions
└── created_at
```

## See Also

- [SpecTrace README](../README.md) - Overall project documentation
- [Current State](current-state.md) - What's implemented
