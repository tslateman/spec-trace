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

The `spectrace tasks` commands drive the Worker's task ledger. Point them at
the Worker with `SPECTRACE_URL` and `SPECTRACE_API_KEY`, or pass `--url` and
`--api-key`.

```bash
export SPECTRACE_URL=https://spectrace.spectrace.workers.dev
export SPECTRACE_API_KEY=...

# 1. Register agents
spectrace tasks register planner-1 --role planner
spectrace tasks register coder-1 --role coder
spectrace tasks register reviewer-1 --role reviewer
spectrace tasks register scorer-1 --role reviewer

# 2. Draft a task, then pass the spec-review gate
spectrace tasks create task-001 --agent planner-1 --title "Lock accounts" \
    --requirement REQ-AUTH-004 --done-when "pytest -k lockout exits 0" \
    --scope-in spectrace/auth/lockout.py
spectrace tasks approve-spec task-001 --reviewer reviewer-1

# 3. Claim and work on it
spectrace tasks list --status unclaimed
spectrace tasks claim task-001 --agent coder-1
spectrace tasks start task-001 --agent coder-1
# ... do the work ...

# 4. Pass the intent gate, then submit
spectrace tasks validate-intent task-001 --validator scorer-1 --commit-sha abc123 \
    --strategic-score 88 --opportunity-score 91 --drift-score 79
spectrace tasks complete task-001 --agent coder-1 --commit-sha abc123

# 5. Review and merge
spectrace tasks review task-001 --reviewer reviewer-1 --decision approved
spectrace tasks merge task-001
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
| `DRAFT`             | Created; leaves only on spec approval   |
| `UNCLAIMED`         | Spec approved, available to claim       |
| `CLAIMED`           | Agent has claimed with a lease          |
| `IN_PROGRESS`       | Agent is actively working               |
| `READY_FOR_REVIEW`  | Work submitted, awaiting review         |
| `CHANGES_REQUESTED` | Reviewer requested changes              |
| `APPROVED`          | Review passed, ready to merge           |
| `MERGED`            | Work merged (terminal)                  |
| `BLOCKED`           | Waiting on dependencies                 |
| `ABANDONED`         | Hypothesis exhausted after max attempts |

## Two intent gates

The Worker gates the pipeline on intent at both ends. A task enters in `DRAFT`
and leaves only when a reviewer approves its spec. A commit reaches
`READY_FOR_REVIEW` only when its latest intent validation passed. Stripe's SDK
team described the same shape: review the spec before implementation begins,
then review the output against the intent
([Stripe, 2026-08-28](https://stripe.dev/blog/ai-didnt-write-our-sdk-it-changed-how-we-built-it)).

| Gate         | Route                                             | Who                        | Refuses with                                                    |
| ------------ | ------------------------------------------------- | -------------------------- | --------------------------------------------------------------- |
| Spec review  | `POST /api/v1/tasks/{task_id}/approve-spec`       | A `reviewer` agent         | `SPEC_INCOMPLETE` (no requirements, `scope_in`, or `done_when`) |
| Intent       | `POST /api/v1/tasks/{task_id}/complete`           | The claiming `coder`       | `INTENT_NOT_VALIDATED`, `INTENT_FAILED`                         |
| Intent score | `POST /api/v1/tasks/{task_id}/intent-validations` | Any agent but the claimant | `SELF_INTENT_NOT_ALLOWED`                                       |

`POST /api/v1/tasks/` creates the draft; only a `planner` agent may call it.
`POST /api/v1/tasks/{task_id}/intent-validations` records the verdict of an
intent evaluation for one commit. `passed` defaults to every score reaching 70,
the threshold `validate_intent` uses. `validator_id` names the agent that
judged, and the Worker refuses the agent holding the task's claim, so a coder
cannot score its own work. `spectrace tasks approve-spec` and `spectrace tasks
validate-intent` drive the two gates from the CLI.

## The linked-test gate

Intent says the commit meant the right thing; the linked tests say it works.
`POST /api/v1/tasks/{task_id}/review` with `approved` refuses with
`LINKED_TESTS_NOT_PASSING` unless every requirement the task links has at least
one test result at the submitted commit and none of them failed. The Worker
matches `requirements_testrun.git_sha` against the task's `commit_sha`, so a run
on main or on an earlier attempt proves nothing about the commit under review.

```json
{
  "error": {
    "code": "transition_error",
    "message": "Task 'task-auth-lockout-001' has no passing linked test run at commit a1b2c3d: REQ-AUTH-004 has no result",
    "details": { "reason": "LINKED_TESTS_NOT_PASSING" }
  }
}
```

`spectrace tasks run` feeds the gate: `{junit}` in `--tests` names the file the
run writes its JUnit XML to, and the runner pushes that file to
`POST /api/v1/results/test-runs/` tagged with the commit it just made, with each
case carrying the requirements the bundle says it verifies. `GET /api/v1/tasks/`
returns the same summary as `test_run` on every submitted task, and the
dashboard's task table shows it.

### A task bounded enough to delegate

Stripe's rule specs carried a name, a purpose, a spec reference, a severity, and
valid and invalid examples. The SpecTrace equivalent is the create body. This
one is complete enough to pass `approve-spec`:

```json
{
  "agent_id": "planner-1",
  "task_id": "task-auth-lockout-001",
  "title": "Lock an account after five failed logins",
  "description": "Count failures per account, not per IP. Reset the count on success.",
  "requirements": ["REQ-AUTH-004"],
  "spec_ref": "specs/auth/login.md#REQ-AUTH-004",
  "done_when": [
    "pytest spectrace/tests/test_auth.py -k lockout exits 0",
    "A sixth attempt within 15 minutes returns 423 with a Retry-After header"
  ],
  "scope_in": ["spectrace/auth/lockout.py", "spectrace/tests/test_auth.py"],
  "scope_out": ["spectrace/notifications/", "The password reset flow"]
}
```

The reviewer reads this, not the code. `done_when` names what correct means
before anyone touches implementation. `scope_out` names the boundary the coder
must not cross. The `spec_ref` points at the requirement's section the way
Stripe's rules pointed at `S-002 Custom Object DDL §4`.

The full path through the Worker:

```bash
BASE=https://spectrace.spectrace.workers.dev/api/v1/tasks
post() {
  curl -sX POST "$BASE/$1" -H "X-API-Key: $SPECTRACE_API_KEY" \
    -H "Content-Type: application/json" -d "$2"
}

post "" @task.json
post task-auth-lockout-001/approve-spec '{"reviewer_id": "reviewer-1", "feedback": "Scope is tight"}'
post task-auth-lockout-001/claim '{"agent_id": "coder-1"}'
post task-auth-lockout-001/start '{"agent_id": "coder-1"}'
post task-auth-lockout-001/intent-validations \
  '{"validator_id": "scorer-1", "commit_sha": "a1b2c3d", "strategic_score": 88, "opportunity_score": 91, "drift_score": 79}'
post task-auth-lockout-001/complete '{"agent_id": "coder-1", "commit_sha": "a1b2c3d"}'
```

The same path from the CLI:

```bash
spectrace tasks create task-auth-lockout-001 --agent planner-1 \
    --title "Lock an account after five failed logins" \
    --description "Count failures per account, not per IP. Reset the count on success." \
    --requirement REQ-AUTH-004 --spec-ref "specs/auth/login.md#REQ-AUTH-004" \
    --done-when "pytest spectrace/tests/test_auth.py -k lockout exits 0" \
    --done-when "A sixth attempt within 15 minutes returns 423 with a Retry-After header" \
    --scope-in spectrace/auth/lockout.py --scope-in spectrace/tests/test_auth.py \
    --scope-out spectrace/notifications/ --scope-out "The password reset flow"
spectrace tasks approve-spec task-auth-lockout-001 --reviewer reviewer-1 --feedback "Scope is tight"
spectrace tasks claim task-auth-lockout-001 --agent coder-1
spectrace tasks start task-auth-lockout-001 --agent coder-1
spectrace tasks validate-intent task-auth-lockout-001 --validator scorer-1 \
    --commit-sha a1b2c3d --strategic-score 88 --opportunity-score 91 --drift-score 79
spectrace tasks complete task-auth-lockout-001 --agent coder-1 --commit-sha a1b2c3d
```

Skip the intent validation and `complete` answers 409. Record one with a score
under 70 and it answers 409 with the failure reasons. Both, from a local run on
2026-09-14:

```json
{"error":{"code":"transition_error","message":"Commit a1b2c3d on task 'task-auth-lockout-001' has no intent validation","details":{"reason":"INTENT_NOT_VALIDATED"}}}
{"error":{"code":"transition_error","message":"Commit a1b2c3d on task 'task-auth-lockout-001' failed intent validation: Tests encode the misread spec","details":{"reason":"INTENT_FAILED"}}}
```

## Agent Roles

| Role       | Can Do                 | Cannot Do       |
| ---------- | ---------------------- | --------------- |
| `planner`  | Create tasks           | Claim or review |
| `coder`    | Claim, start, submit   | Review          |
| `reviewer` | Review, approve/reject | Claim           |

**Self-review is prohibited**: The agent who submitted work cannot review it.

## CLI Commands

Every `spectrace tasks` command calls the Worker, so the spec gate and the
intent gate hold for CLI callers. Each takes `--url` and `--api-key` (or
`SPECTRACE_URL` and `SPECTRACE_API_KEY`) and `--format text|json`.

| Command                           | Endpoint                                                                 | Moves the task                      |
| --------------------------------- | ------------------------------------------------------------------------ | ----------------------------------- |
| `tasks register <agent_id>`       | `POST /api/v1/tasks/agents/register/`                                    | —                                   |
| `tasks create <task_id>`          | `POST /api/v1/tasks/`                                                    | into `draft`                        |
| `tasks plan`                      | `POST /api/v1/tasks/`                                                    | into `draft`, one task per source   |
| `tasks approve-spec <task_id>`    | `POST /api/v1/tasks/{task_id}/approve-spec`                              | `draft` → `unclaimed`               |
| `tasks list`                      | `GET /api/v1/tasks/`                                                     | —                                   |
| `tasks claim <task_id>`           | `POST /api/v1/tasks/{task_id}/claim`                                     | `unclaimed` → `claimed`             |
| `tasks start <task_id>`           | `POST /api/v1/tasks/{task_id}/start`                                     | `claimed` → `in_progress`           |
| `tasks validate-intent <task_id>` | `POST /api/v1/tasks/{task_id}/intent-validations`                        | —                                   |
| `tasks complete <task_id>`        | `POST /api/v1/tasks/{task_id}/complete`                                  | → `ready_for_review`                |
| `tasks review <task_id>`          | `POST /api/v1/tasks/{task_id}/review`                                    | → `approved` or `changes_requested` |
| `tasks merge <task_id>`           | `GET /api/v1/tasks/{task_id}`, then `POST /api/v1/tasks/{task_id}/merge` | `approved` → `merged`               |
| `tasks release <task_id>`         | `POST /api/v1/tasks/{task_id}/release`                                   | → `unclaimed`                       |
| `tasks context <task_id>`         | `GET /api/v1/tasks/{task_id}/context`                                    | —                                   |

### `tasks register`

Register an agent, or update its role and reactivate it.

```bash
spectrace tasks register <agent_id> --role <planner|coder|reviewer> [--config '{"key": "value"}']

# Examples
spectrace tasks register coder-opus --role coder --config '{"model": "claude-opus-4"}'
spectrace tasks register reviewer-1 --role reviewer
```

### `tasks create`

Record a draft task. Only a `planner` agent may create one. Repeat
`--requirement`, `--done-when`, `--scope-in`, and `--scope-out` for each entry;
`approve-spec` refuses a task that names none of the first three.

```bash
spectrace tasks create <task_id> --agent <planner_id> --title <title> \
    [--description <text>] [--requirement REQ-ID]... [--done-when <criterion>]... \
    [--scope-in <path>]... [--scope-out <path>]... [--spec-ref <ref>] [--max-attempts 2]
```

**Errors:**

- `ROLE_NOT_ALLOWED`: Only planners create tasks
- `REQUIREMENT_NOT_FOUND`: A `--requirement` id the Worker has never seen
- `TASK_EXISTS`: The task id is taken

### `tasks plan`

Draft tasks from a roadmap item or from the requirements no test covers, with
`requirements`, `scope_in`, and `done_when` filled so `approve-spec` has
something to judge. The command creates drafts and approves none: a person still
reviews each one.

```bash
spectrace tasks plan --agent <planner_id> --item <number or title text> \
    [--roadmap ROADMAP.md] [--repo .] [--requirement REQ-ID]... \
    [--scope-in <path>]... [--scope-out <path>]... [--prefix plan] [--dry-run]

spectrace tasks plan --agent <planner_id> --gaps \
    [--project <name>] [--limit 5] [--scope-in <path>]...
```

`--item` reads one numbered roadmap item. Its heading becomes the title, its
prose becomes the description, its **Done when:** sentence splits into
`done_when` criteria, and the paths it names that the checkout holds become
`scope_in`. Roadmap prose names no requirement, so `--requirement` supplies it.

`--gaps` asks the Worker for the requirements it reports as `untested` and
drafts one task per requirement, scoped to the requirement's spec file.

Both refuse before posting when a draft would reach the Worker without
requirements, `scope_in`, or `done_when`, naming the same fields the Worker's
`SPEC_INCOMPLETE` refusal names. `--dry-run` prints the drafts as JSON and
creates none.

```bash
$ spectrace tasks plan --agent planner-1 --item 5 --requirement REQ-PLAT-002
Drafted plan-5-refresh-the-planning-record in draft: Refresh the planning record
1 awaiting spec approval

$ spectrace tasks plan --agent planner-1 --gaps --project spectrace --limit 2 --prefix gap
Drafted gap-req-bill-001 in draft: Cover REQ-BILL-001 with a passing linked test
Drafted gap-req-bill-002 in draft: Cover REQ-BILL-002 with a passing linked test
2 awaiting spec approval
```

**Errors:**

- `ROLE_NOT_ALLOWED`: Only planners create tasks
- `REQUIREMENT_NOT_FOUND`: A `--requirement` id the Worker has never seen
- `TASK_EXISTS`: The prefix and source already produced this task id

### `tasks approve-spec`

Pass the spec-review gate. Requires `reviewer` role.

```bash
spectrace tasks approve-spec <task_id> --reviewer <agent_id> [--feedback "text"]
```

**Errors:**

- `SPEC_INCOMPLETE`: The task names no requirements, `scope_in`, or `done_when`
- `NOT_DRAFT`: The task has already left `draft`

### `tasks list`

List tasks a page at a time.

```bash
spectrace tasks list [--status STATUS] [--page N] [--per-page N] [--sort FIELDS] [--format json]

# Examples
spectrace tasks list                           # Newest first
spectrace tasks list --status unclaimed        # Available work
spectrace tasks list --sort -priority,title    # `-` prefix sorts descending
spectrace tasks list --format json             # {"data": [...], "meta": {...}}
```

### `tasks claim`

Claim an unclaimed task. Creates a lease (default 30 minutes).

```bash
spectrace tasks claim <task_id> --agent <agent_id> [--lease-minutes 30]

# Example
spectrace tasks claim task-auth-001 --agent coder-1 --lease-minutes 60
```

**Errors:**

- `ROLE_NOT_ALLOWED`: Only coders can claim
- `AGENT_BUSY`: Agent already has a task in progress
- `DEPENDENCIES_NOT_MET`: Blocking tasks not merged
- `INVALID_TRANSITION`: The task is still in `draft`

### `tasks start`

Begin work on a claimed task.

```bash
spectrace tasks start <task_id> --agent <agent_id>
```

### `tasks validate-intent`

Record the verdict of an intent evaluation for one commit. Every score is 0 to
100; the verdict passes when every score reaches 70 unless `--passed` or
`--failed` overrides it.

`--validator` names the agent that judged the commit. The Worker refuses the
agent holding the task's claim with `SELF_INTENT_NOT_ALLOWED`, so a coder
cannot score its own work.

```bash
spectrace tasks validate-intent <task_id> --validator <agent_id> --commit-sha <sha> \
    --strategic-score N --opportunity-score N --drift-score N \
    [--passed | --failed] [--failure-reason "text"]...

# Example
spectrace tasks validate-intent task-auth-001 --validator scorer-1 --commit-sha a1b2c3d \
    --strategic-score 40 --opportunity-score 91 --drift-score 79 \
    --failure-reason "Tests encode the misread spec"
```

**Errors:**

- `SELF_INTENT_NOT_ALLOWED`: The validator is the agent that claimed the task
- `AGENT_NOT_FOUND`: No agent carries that id

### `tasks complete`

Submit work for review with a commit SHA. The commit's latest intent
validation must have passed.

```bash
spectrace tasks complete <task_id> --agent <agent_id> --commit-sha <sha>

# Example
spectrace tasks complete task-auth-001 --agent coder-1 --commit-sha a1b2c3d4e5f6
```

**Errors:**

- `INTENT_NOT_VALIDATED`: No intent validation covers this commit
- `INTENT_FAILED`: The commit's latest intent validation failed
- `NOT_OWNER`: Another agent holds the claim

### `tasks review`

Review submitted work. Requires `reviewer` role.

```bash
spectrace tasks review <task_id> --reviewer <agent_id> --decision <decision> \
    [--feedback "text"] [--blocking-issues "issue1" --blocking-issues "issue2"] [--suggestions "idea1"]

# Examples
spectrace tasks review task-auth-001 --reviewer reviewer-1 --decision approved --feedback "LGTM"

spectrace tasks review task-auth-001 --reviewer reviewer-1 --decision changes_requested \
    --feedback "Tests missing" --blocking-issues "Add unit tests for edge cases"
```

**Decisions:**

- `approved` → Task moves to APPROVED; refused with `LINKED_TESTS_NOT_PASSING` when the task's requirements have no passing test run at the submitted commit
- `changes_requested` → Task moves to CHANGES_REQUESTED (can resubmit); the `max_attempts`th one moves it to ABANDONED
- `rejected` → Refused with `INVALID_TRANSITION`; the state machine has no `ready_for_review` to `abandoned` edge

### `tasks merge`

Merge an approved task's branch into the base branch, then record the merge on
the task. The state follows the git fact: every check runs before git is
touched, so a task that cannot merge leaves the repository as it was.

```bash
spectrace tasks merge <task_id> [--repo .] [--base main] [--branch <name>] [--remote origin]
```

The branch comes from the task, which records it when the coder submits. Name
one with `--branch` for a task submitted before the ledger kept it; a name that
contradicts the ledger is refused.

| Refusal            | What it means                                              |
| ------------------ | ---------------------------------------------------------- |
| `NOT_APPROVED`     | The task has not passed review                             |
| `BRANCH_UNKNOWN`   | The ledger records no branch and none was named            |
| `BRANCH_MISMATCH`  | `--branch` contradicts the branch the ledger recorded      |
| `NOT_ON_BASE`      | The repository sits on another branch                      |
| `REPO_DIRTY`       | The working tree has uncommitted changes                   |
| `BRANCH_NOT_FOUND` | The repository, or the remote, has no such branch          |
| `BRANCH_DRIFTED`   | The branch moved since the review read it                  |
| `MERGE_CONFLICT`   | The merge conflicts; git is aborted and the base unchanged |
| `WORKER_REFUSED`   | The Worker refused the read or the record                  |

`BRANCH_DRIFTED` is the safety property. The reviewed commit is what the
reviewer read and what the linked tests ran against; a branch that moved since
carries work nobody approved, so coverage on the base branch would stop being
the coverage the task claimed.

The Worker asserts the same fact. `POST /api/v1/tasks/{task_id}/merge` carries
`merge_sha` and `branch_head_sha`, and refuses `BRANCH_DRIFTED` when
`branch_head_sha` differs from the commit the review read. The CLI checks first,
so no caller of `tasks merge` reaches that refusal; a caller posting by hand
does.

Rerunning after a merge that landed but went unrecorded is safe: git reports the
branch already merged, and the command records the merge commit that is already
there.

### `tasks context`

Assemble the bundle an agent reads before it works a task: task details,
linked specs with their tree placement, test results, and FRET fields, and
drift over the whole database.

The Worker assembles the bundle; the CLI renders the markdown and adds the
Lore overlay, because the Worker has no subprocess. `--format json` emits the
Worker's bundle with the overlay under a `lore` key.

```bash
spectrace tasks context <task_id> [--format text|json] [--output <path>] [--no-lore]
```

**Options:**

| Flag        | Default | Description                                  |
| ----------- | ------- | -------------------------------------------- |
| `--format`  | `text`  | Output format: `text` (markdown) or `json`   |
| `--output`  | —       | Write output to file (in addition to stdout) |
| `--no-lore` | off     | Skip the Lore overlay                        |

**Errors:**

- `not_found`: The ledger holds no task with that id

**Lore integration:** When the Lore CLI is available (`LORE_CLI` env var or
`lore` on `PATH`), the bundle gains a Lore Context section with decisions,
patterns, and failures matching the linked specs' tags and titles. When Lore
is absent or the query fails, the command succeeds and omits the section. The
subprocess has a 30-second timeout.

**Examples:**

```bash
# Markdown bundle to stdout
spectrace tasks context TASK-001

# JSON output
spectrace tasks context TASK-001 --format json

# Write to file for agent handoff
spectrace tasks context TASK-001 --output /tmp/context.md
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

### `tasks release`

Drop the claim and lease, returning the task to UNCLAIMED. The ledger's lease
alarm calls the same endpoint with reason `lease_expired`.

```bash
spectrace tasks release <task_id> [--reason manual]
```

### `tasks run`

Drain the unclaimed queue without a person at the keyboard. For each task, in
creation order, the runner claims and starts it, reads its context bundle,
adds a worktree at `<worktrees>/<task_id>` on branch `task/<task_id>` off
`--base`, runs `--coder` there with the bundle as JSON on stdin, runs
`--tests`, commits whatever the coder changed, pushes the test results tagged
with that commit, and submits it for review. It stops at the first refusal, from the Worker or from a command, and
prints the task id, the stage, and the reason.

```bash
spectrace tasks run --agent coder-1 --repo . \
    --coder 'claude -p "$(cat)"' \
    --tests 'pytest {linked} --junitxml={junit}' \
    --scorer ./score-intent.sh \
    --scorer-agent scorer-1 \
    --limit 3
```

`{linked}` in `--tests` expands to the ids of every test linked to the task's
requirements; a task with no linked test refuses at the tests stage. `{junit}`
expands to a path beside the worktree, and after the commit the runner pushes
that JUnit XML to the Worker tagged with the commit sha and the task branch, so
`review --decision approved` can require it later. A `--tests` command that
names `{junit}` and writes nothing there refuses at the results stage.
`--scorer`
is optional: it receives the bundle, commit sha, and diff as JSON on stdin and
prints `strategic_score`, `opportunity_score`, `drift_score`, and optional
`failure_reasons` as JSON, which the runner records with `validate-intent`
before submitting. Without a scorer, `complete` refuses with
`INTENT_NOT_VALIDATED` and the runner stops there.

`--scorer-agent` names the agent the verdict is posted under. It is required
with `--scorer` and must differ from `--agent`, because the Worker refuses an
intent result from the agent holding the claim.

A rerun after a crash reuses the task's worktree and branch, so nothing about
the attempt lives only in the ledger. After a refusal the task stays claimed by
the agent, and a coder holds one task at a time, so a second run with the same
agent refuses with `AGENT_BUSY`. Fix the cause, then `tasks release` the task
or finish it by hand.

**Exit codes:** `0` means the runner submitted every task it drained, and an
empty queue counts. `1` means the loop stopped at a refusal, and the message
names the task, the stage, and the reason; `--format json` prints the same
three fields as an object. Tasks the runner never reached stay UNCLAIMED, so a
later run picks them up.

#### Hosting the runner

`.github/workflows/runner.yml` runs the loop on GitHub Actions every 30 minutes
and on demand, one job at a time. It installs the CLI, prints the unclaimed
queue, and, when `CLAUDE_CODE_OAUTH_TOKEN` is set, drains one task with
`scripts/task-coder.sh` as the coder and `scripts/task-scorer.sh` as the
scorer. Both wrap `claude -p`; the scorer runs as its own process with the
task, its requirements, and the diff, and nothing from the coder's session. It
registers `gha-coder` and `gha-scorer` and posts the verdict as the second, so
the Worker's `SELF_INTENT_NOT_ALLOWED` gate holds on Actions too.
Set `dry_run` when dispatching to stop after the queue listing.

The token comes from a Claude subscription, not an API key: run
`claude setup-token` once on a machine that is logged in, and store what it
prints as the `CLAUDE_CODE_OAUTH_TOKEN` repository secret. The job runs
Claude Code itself, which is where that token is allowed to be used.

Actions keeps no disk between jobs, so the workflow passes `--remote origin`:
the runner fetches `task/<id>` from the remote before creating the worktree
and pushes the branch after every commit. A job that dies mid-task leaves the
branch on origin, and the next job resumes from it.

Worker-only commands, the `tasks` group among them, no longer configure
Django, so a job needs no database and no settings module. On the Actions
runner the CLI installs in 3 seconds with uv, measured on the Worker
workflow's push job, which runs the same install line.

One live run on 2026-09-15 against a local Worker, coder and scorer both
`claude -p`, task "Document the exit codes of spectrace tasks run" scoped to
this file:

```
$ spectrace tasks run --agent coder-live-213112 --repo . --base feature/runner-actions \
    --coder scripts/task-coder.sh --tests 'ruff check spectrace && prettier --check docs/agent-tasks.md' \
    --scorer scripts/task-scorer.sh --limit 1
task-live-213112: working in …/tasks-live/task-live-213112 on task/task-live-213112
task-live-213112: submitted 7579a8a for review
```

Seven minutes end to end. The "Exit codes" paragraph above is that commit,
cherry-picked from the task branch.

Two runs against a local Worker on 2026-09-15, both tasks approved and linked
to `REQ-TASK-002`. The first has no scorer, so the Worker refuses the submit;
the second scores and submits:

```
$ spectrace tasks run --agent coder-1 --repo . --base feature/task-runner --coder "$CODER" --tests "$TESTS"
task-205928-a: working in /private/tmp/claude-501/-Users-tslater-dev-spec-trace-cloudflare/991edf7e-812c-478f-9ea5-f91f4070ba5f/scratchpad/tasks/task-205928-a on task/task-205928-a
Error: task-205928-a: complete refused: INTENT_NOT_VALIDATED
exit 1

$ spectrace tasks run --agent coder-2 --repo . --base feature/task-runner --coder "$CODER" --tests "$TESTS" --scorer ./score.sh
task-205928-b: working in /private/tmp/claude-501/-Users-tslater-dev-spec-trace-cloudflare/991edf7e-812c-478f-9ea5-f91f4070ba5f/scratchpad/tasks/task-205928-b on task/task-205928-b
task-205928-b: submitted 2c7b401 for review

task-205928-b ready_for_review coder-205928-2
task-205928-a in_progress coder-205928-1
```

## Management commands (retiring)

### `expire_leases`

Runs through `python manage.py` only and retires with the Django server.
Releases Django-stored tasks with expired leases. The Worker needs no cron: its
ledger alarm releases an expired lease on its own.

```bash
python manage.py expire_leases [--dry-run] [--format json]
```

## Leases and Timeouts

When an agent claims a task, a **lease** is created with an expiration time (default 30 minutes). This prevents abandoned claims from blocking work.

If the lease expires:

- The ledger's lease alarm releases the task back to UNCLAIMED
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

All commands support `--format json` for CI/script integration. A success
prints the Worker's `data` object; a refusal prints the Worker's error
envelope and exits 1.

```bash
# Claim task and parse result
result=$(spectrace tasks claim task-001 --agent coder-1 --format json)
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

**Failed claim** (exit code 1):

```json
{
  "error": {
    "code": "transition_error",
    "message": "Agent 'coder-1' already has task 'task-002' in progress",
    "details": {
      "reason": "AGENT_BUSY"
    }
  }
}
```

In text mode the same refusal prints one line to stderr:

```
Error: 409 from https://.../api/v1/tasks/task-001/claim: Agent 'coder-1' already has task 'task-002' in progress [AGENT_BUSY]
```

## Typical Workflow

### Coder Agent

```bash
#!/bin/bash
AGENT_ID="coder-1"

# 1. Find available work
task=$(spectrace tasks list --status unclaimed --format json | jq -r '.data[0].id')

# 2. Claim it
spectrace tasks claim "$task" --agent "$AGENT_ID"

# 3. Start work
spectrace tasks start "$task" --agent "$AGENT_ID"

# 4. Do the work (git operations, code changes, etc.)
# ...

# 5. Record the intent evaluation, then submit for review
commit_sha=$(git rev-parse HEAD)
spectrace tasks validate-intent "$task" --validator scorer-1 --commit-sha "$commit_sha" \
    --strategic-score 88 --opportunity-score 91 --drift-score 79
spectrace tasks complete "$task" --agent "$AGENT_ID" --commit-sha "$commit_sha"
```

### Reviewer Agent

```bash
#!/bin/bash
AGENT_ID="reviewer-1"

# 1. Approve any draft whose spec is complete
task=$(spectrace tasks list --status draft --format json | jq -r '.data[0].id')
spectrace tasks approve-spec "$task" --reviewer "$AGENT_ID"

# 2. Find tasks ready for review
task=$(spectrace tasks list --status ready_for_review --format json | jq -r '.data[0].id')

# 3. Review the code (automated checks, etc.)
# ...

# 4. Approve or request changes
spectrace tasks review "$task" --reviewer "$AGENT_ID" --decision approved
```

## Error Codes

| Code                      | Meaning                                      |
| ------------------------- | -------------------------------------------- |
| `AGENT_NOT_FOUND`         | Agent ID doesn't exist                       |
| `AGENT_INACTIVE`          | Agent is deactivated                         |
| `TASK_NOT_FOUND`          | Task ID doesn't exist                        |
| `INVALID_TRANSITION`      | State change not allowed                     |
| `ROLE_NOT_ALLOWED`        | Agent role cannot perform action             |
| `AGENT_BUSY`              | Agent already has active task                |
| `DEPENDENCIES_NOT_MET`    | Blocking tasks not merged                    |
| `NOT_OWNER`               | Agent doesn't own this task                  |
| `NOT_READY_FOR_REVIEW`    | Task not in READY_FOR_REVIEW state           |
| `NOT_APPROVED`            | Task not in APPROVED state                   |
| `SELF_REVIEW_NOT_ALLOWED` | Cannot review own work                       |
| `SELF_INTENT_NOT_ALLOWED` | Cannot score the intent of own work          |
| `NOT_DRAFT`               | Spec approval on a task past DRAFT           |
| `SPEC_INCOMPLETE`         | No requirements, scope_in, or done_when      |
| `INTENT_NOT_VALIDATED`    | No intent validation for the commit          |
| `INTENT_FAILED`           | The commit's latest intent validation failed |
| `TASK_EXISTS`             | Task ID already taken                        |
| `REQUIREMENT_NOT_FOUND`   | Requirement ID doesn't exist                 |

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
├── scope_in, scope_out (JSON lists)
├── spec_ref
├── requirements (M2M → Requirement)
├── depends_on (M2M self-referential)
└── sprint → AgentSprint

IntentValidationResult
├── task → AgentTask
├── commit_sha
├── strategic_score, opportunity_score, drift_score
├── passed
├── failure_reasons (JSON list)
└── created_at

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
