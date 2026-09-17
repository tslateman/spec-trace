# Roadmap

What SpecTrace does next, in priority order. This file is the authority for
open work. `.planning/STATE.md` tracks the current position,
`.planning/MILESTONES.md` archives shipped milestones, and
[CHANGELOG.md](CHANGELOG.md) records what landed. When those disagree with this
file about what comes next, this file wins.

Last reviewed: 2026-09-16.

## Now

### 1. Finish the Cloudflare cutover

Underway, not hypothetical: the Worker serves production, CI deploys it on
merge to main, and the push job feeds it specs, links, flows, and JUnit
results. [plans/cloudflare-port.md](plans/cloudflare-port.md) carries the
measured state of every phase and success criterion.

One thing remains: stopping the Django server. CI pushes impact and drift
reports as of 2026-09-16, so the dashboard reads what the Worker holds. The API key guards every `/api/` route, PR #2 retired the
Worker screens on 2026-09-10 in favor of the dashboard, and
`worker/test/contract.test.ts` now fails CI when the Worker serves an
operation the contract omits or omits one it names.

Every `spectrace tasks` command now calls the Worker, so the spec-approval
and intent gates hold for every caller (shipped 2026-09-14), and `tasks
context` joined them on 2026-09-15 through `GET
/api/v1/tasks/{task_id}/context`. A Worker-only command no longer starts
Django: `_run` and the ORM-backed services bootstrap for themselves, so
`spectrace tasks list` runs with no local database.

Four groups of tables sat empty in D1 for want of a push path. Tommy settled
which the CLI pushes and which the Worker writes on 2026-09-15, and three of
the four now have a path:

- **SLOs and their requirement links.** `spectrace push --slos DIR` writes the
  definitions through `PUT /api/v1/slos/`, so `POST
  /api/v1/integrations/slo/status/` finds a row to update by name instead of
  missing every time. Shipped in #11.
- **Corpus entries and versions.** `spectrace push --corpus DIR` writes them
  through `PUT /api/v1/corpus/entries/`. Shipped in #12. Snapshots stay
  Worker-written: a snapshot records the versions a review ran against, and
  the pushing side does not know what the store holds, so `corpus_review.py`
  captures it where the versions are.
- **Flow runs and steps.** The CLI pushes these next, on the same pattern.

**Agent tasks created outside the Worker get no push path, by design.** The
TaskLedger Durable Object is single-writer by construction, which is what makes
a claim atomic without a transaction dance; a push path is a second writer and
reintroduces the race the ledger exists to prevent. The Django rows are
pre-Worker history -- migrate them once or let them go.

**Done when:** every success criterion in the plan is met and the Django server
is stopped.

## Next

### 2. Coverage trend snapshots

`spec_coverage` reports today's numbers and forgets them. `CorpusSnapshot`
stores corpus versions; nothing stores coverage over time. Deferred out of v10
Phase 2 and still the blocker under the trends chart.

**Done when:** a snapshot model records each `spec_coverage` run, the command
reports change against the previous snapshot, and the dashboard charts the
series.

### 3. Grow the corpus beyond four domains

`corpus/` holds billing, identity, platform, and security. Coverage claims are
worth what the corpus covers. Decide which standards, decisions, and
commitments belong in it next, so a moved standard fails a build instead of
aging quietly.

This item also owns `corpus drift --strict` in CI. Corpus entries scope through
`applies_to.paths`, so none match a SpecTrace spec until a corpus for
SpecTrace's own domain lands in `meta/corpus/`.

**Done when:** the corpus covers the domains the specs actually touch, and CI
fails on a stale review.

### 4. Link tests in every language the repo tests in

The pytest marker was the only way to link a test until 2026-09-15, so the
Worker's own vitest suite verified nothing. A bracketed requirement ID in a
test name now links from any runner that writes JUnit XML, and CI pushes the
Worker suite's links and results that way. Python and TypeScript have worked
examples in README.md; Go and Rust do not.

**Done when:** README.md shows a linked test and its runner config for Python,
TypeScript, Go, and Rust, and an example project per language pushes its
links and results in CI.

### 5. Refresh the planning record

`docs/current-state.md` was refreshed 2026-09-09 and describes the Cloudflare
port. The planning record lags it. `.planning/MILESTONES.md` last changed
2026-02-03 and stops at v9. `.planning/STATE.md` gained a lag notice on
2026-09-09, but its milestone table stops at v9 and its session log at
2026-02-28. Neither records v0.11.0 or the port. The one-repo-per-ref-pair
fix (shipped 2026-09-15) exists because the docs and the code disagreed.

**Done when:** `consolidate` regenerates `current-state.md` from the live
database, and STATE.md and MILESTONES.md carry the milestone this roadmap's
"Now" section produces.

### 6. Carry the Linear integration to the CLI

Decided 2026-09-15: Linear runs outside Django, and no server holds the token.
The CLI pulls and reports; the Worker never learns Linear exists.

Shipped the same day as `spectrace linear`. `pull` fetches issues by label and
pushes them to the Worker as requirements, `report` tallies a JUnit run per
requirement and posts the counts as an issue comment plus a `tests:passing` or
`tests:failing` label, and `check` verifies the token's shape, identity, and
read access. The two management commands are deleted.

Four modules moved so the path imports with no database: the Linear client
dropped its `VerificationMethod` import, `linear_checks.py` holds the three
pure checks `health.py` re-exports, `junit_cases.py` holds the JUnit case
readers, and `link_records.py` holds `requirement_ids_of`.

What remains: CI runs no reporter, because the repository has no
`LINEAR_API_KEY` secret. Django still serves
`GET /api/v1/integrations/linear/health/`, which dies with the server in item
1 rather than needing its own removal.

**Done when:** a CI job runs `spectrace linear report` after results land.

Items 7 through 13 turn the task ledger into a loop that runs unattended.
Every transition exists today as a state and a CLI command; a person types
each one. 7 through 9 make the loop turn, 10 and 11 make its output
trustworthy, 12 and 13 say whether to keep feeding it.

### 7. Run the task loop unattended

Shipped 2026-09-15 as `spectrace tasks run`: it drains the unclaimed queue,
one worktree and branch per task, hands the context bundle to the `--coder`
command, runs `--tests` with `{linked}` expanded to the linked test ids,
commits, scores through `--scorer` when given, submits, and stops at the
first refusal with the task id, stage, and reason. Proven against a local
Worker; see `docs/agent-tasks.md`.

Hosted the same day on GitHub Actions: `runner.yml` runs every 30 minutes
and on demand, `scripts/task-coder.sh` and `scripts/task-scorer.sh` wrap
`claude -p`, and `--remote origin` lets a job resume a task branch another
job started. One live run, coder and scorer both Claude, took seven minutes
from unclaimed to `ready_for_review`. The CLI installs in 3 seconds on the
runner, so the Django dependency costs nothing there; Worker-only commands
no longer configure it either.

What remains here: the ledger records neither the worktree nor the branch, so
the runner derives both from the task id. Linked tests are pytest ids in the
workflow's test command; the Worker's vitest ids need their own runner. The
queue is empty until item 8 drafts something, so the schedule finds no work.

`CLAUDE_CODE_OAUTH_TOKEN` became a repository secret on 2026-09-15, and the
first dispatch after it died with `ModuleNotFoundError` because `run` imported
its service before setting the package paths up. Fixed the same day; a full
dispatch then registered `gha-coder` and drained an empty queue.

**Done when:** a task drafted by item 8 reaches `ready_for_review` on Actions
with no command typed by hand.

### 8. Draft tasks from the roadmap and the gaps

Drafts come from a person typing `spectrace tasks create`. A planner agent
should produce them from a roadmap item, an untested requirement, or a
drift report, with `scope_in` and `done_when` filled so spec approval has
something to judge. Spec approval stays with a person. That is the one
station worth one.

**Done when:** `spectrace tasks plan` turns a named roadmap item or the
current `spec_coverage` gaps into draft tasks that pass the SPEC_INCOMPLETE
check, and a reviewer approves or rejects each one from the dashboard.

### 9. Score intent with an agent that never sees the coder's context

`POST /api/v1/tasks/{id}/intent-validations` stores three scores and passes
at 70. `spectrace tasks validate-intent` takes the scores as options, so
whoever calls it is the judge, and today that is the coder. A second agent
reads the spec and the diff, with none of the coder's transcript, and posts
the score.

The first half shipped with item 7: `scripts/task-scorer.sh` runs as its own
`claude -p` process with the task, its requirements, and the diff, and none
of the coder's session. The Worker still accepts an intent result from any
caller.

**Done when:** a coder cannot post its own intent result.

Shipped 2026-09-16. `POST /api/v1/tasks/{id}/intent-validations` takes a
`validator_id`, resolves it against the `agents` table, and refuses with
`SELF_INTENT_NOT_ALLOWED` when that agent holds the task's claim. `runner.yml`
registers `gha-scorer` as a reviewer and passes `--scorer-agent`, so the hosted
loop scores under an identity the coder does not use.

What holds is narrower than the sentence above, and the difference is worth
keeping: a coder that identifies itself honestly cannot score its own commit; a
coder that names another registered agent still can. `validator_id` is
caller-supplied and `api-key.ts` authenticates one shared `SPECTRACE_API_KEY`,
so the Worker has no caller identity independent of the request body. The gate
makes independent scoring the structural default. Closing the spoof is the
per-agent credentials item below.

### 10. Run linked tests on the task branch and feed the ledger

CI verifies main. A task branch never gets its linked tests run at its
commit, and `submitForReview` checks intent but not a test run. The merge
gate should require that the task's requirements have passing linked tests
at the submitted SHA.

**Done when:** the branch build pushes its JUnit results tagged with the
task's SHA, `approve` refuses a task whose requirements lack a passing run
at that SHA, and the task page shows the run.

### 11. Make merged mean merged

`spectrace tasks merge` moves the task to `merged` and touches no branch.
The state should follow the git fact, not precede it, so coverage on main
is the coverage the task claimed.

**Done when:** the merge command merges the branch into main, records the
merge SHA on the task, and refuses when the branch has drifted from the
reviewed commit.

### 12. Prove the outcome loop

Every merged or abandoned outcome should reach Lore's journal after one run
of `spectrace lore sync`. The Worker half has outbox tests; the CLI half has
never run end to end because no task has merged through production. This is
the port plan's one unproven criterion. Until it holds, the next task learns
nothing from the last.

**Done when:** a task merged through item 11 appears in Lore after one sync,
and the next task's context bundle cites it.

### 13. Report on the factory

Nothing reports throughput, refusals per gate, time in each state, or intent
scores over time, so nobody can say whether the loop produces or spins.

**Done when:** the dashboard shows tasks per week by final state, refusals
by gate code, median time per state, and the intent score series, and one
number per week says how many merged tasks later failed a linked test.

## Later

- **Tag the three milestones that never shipped one.** `v0.2.0`, `v0.5.0`, and
  `v0.10.0` have CHANGELOG sections and no tag. Placing them means finding the
  commit each milestone ended on; `.planning/MILESTONES.md` records a git range
  for some, and stops at v9.

- **Route the GitHub webhook, then retire its legacy path.** Two things hold
  here. `webhook_urlpatterns` never reaches `ROOT_URLCONF` --
  `spectrace/spectrace/urls.py` adds only the admin and API patterns, so the
  handler has never served a request in the bundled project. And
  `/api/webhooks/github/` stays a live alias rather than a redirect, because
  GitHub records a redirected delivery as a failure and drops the payload.
  Route the handler first; flip the alias to `redirect_to_v1` once the GitHub
  App points at `/api/v1/integrations/webhooks/github/`.

- **CI webhooks for test results.** ~~The GitHub webhook handler exists for
  events; JUnit results still arrive through `import_results`.~~ Superseded by
  the Cloudflare port: CI pushes its JUnit report to `POST
/api/v1/results/test-runs/` after every deploy, so results reach the server
  without a webhook.
- **Flow scenarios against real integrations.** The Scenario DSL runs flows;
  vendor scenarios are still demo data.

- **Say whose obligation a corpus entry is.** `spectrace push --corpus DIR`
  takes one directory, so pushing `corpus/` and `meta/corpus/` is two
  invocations, and `PUT /api/v1/corpus/entries/` lands both in one namespace.
  Product obligations and SpecTrace's own obligations then interleave with
  nothing distinguishing them, so a dashboard reading corpus entries cannot
  tell "our customers are promised this" from "we promise this about our
  tool." Either `--corpus` repeats, or the two trees push under distinct
  projects. It is a modelling decision about the Worker, not about the corpus
  content.

  **Done when:** a reader of the corpus entries can tell which tree an entry
  came from, and the dashboard groups them accordingly.

- **Stop `spectrace_client` from importing Django admin.** Item 1 records that
  a Worker-only command no longer starts Django. That holds for `_run` and the
  ORM-backed services, and stops holding the moment a command builds the Worker
  client: `spectrace/spectrace_client/__init__.py` imports
  `create_validation_action` from `.admin` at module level, so `from
  spectrace_client.client import ValidationClient` pulls Django admin into every
  command that talks to the Worker, database or not. It configures no settings,
  so nothing breaks today and the cost is import time and a dependency the
  package claims not to need.

  **Done when:** importing `ValidationClient` imports no Django module, and a
  test asserts it by checking `sys.modules` after a fresh import.

- **Generate the command list in `current-state.md` instead of typing it.**
  `consolidate` regenerates the block between its markers, and two command
  blocks sit outside them -- the task-pipeline CLI list and the Quick
  Reference. Both drifted a third time by 2026-09-16, still naming
  `agent-register`, `parse-specs` and `import-results` after all three were
  renamed. Every new command needs a hand patch that regeneration will not
  make. Widening the markers so the list comes from the Click tree retires the
  patch.

  **Done when:** adding a command to `spectrace/cli.py` and running
  `consolidate` updates `current-state.md` with no hand edit.

- **Give each agent its own credential.** `api-key.ts` authenticates every
  `/api/` route against one shared `SPECTRACE_API_KEY`, so the Worker knows a
  request is authorized and never who sent it. Every per-agent rule therefore
  rests on an id in the request body: item 9's intent gate refuses the agent
  named as `validator_id`, and a caller that names a different registered agent
  walks past it. A key or token per registered agent turns identity from
  asserted into presented, and every gate keyed on an agent gets stronger at
  once.

  **Done when:** an agent authenticates as itself, the Worker derives the actor
  from the credential rather than the body, and item 9's gate refuses a coder
  that names the scorer.

- **Stop the changelog gate from blocking a pull request.** `ci.yml` regenerates
  CHANGELOG.md and commits it on every push to main, and demands the same
  regeneration by hand from every pull request. The `check` step fails the PR;
  the author runs `scripts/changelog.py update`, commits CHANGELOG.md alone,
  and pushes again to re-run CI -- for a file the main-branch job rewrites
  seconds after the merge. Three pull requests carried that hand-written commit
  on 2026-09-15, and #8 failed CI first for want of one. Six agents now open
  pull requests against this repository.

  The comment on the check names the real constraint: a fork's pull request
  carries a read-only token, so the job cannot push there. Every pull request
  this repository has seen comes from a branch inside it.

  **Done when:** a pull request from a branch in this repository passes CI with
  no hand-written changelog commit, a fork's pull request still reports the gap
  it cannot close itself, and main's entries stay complete.

- **Fix the concurrent-claim flake.**
  `spectrace/requirements/tests/test_agent_tasks_service.py::TestClaimTask::test_claim_task__concurrent_claims_do_not_crash`
  fails intermittently in CI with `sqlite3.OperationalError: database table is
  locked: requirements_agenttask`, thrown from a worker thread. The assertion
  that surfaces it is `assert outcomes == {"success", "error"}` seeing `set()`.
  It cost two sessions time on 2026-09-15, and sessions now pass the rerun
  advice to each other by hand. Every rerun spends someone's attention deciding
  whether their own branch caused it.

## Not doing

Decided against, with the reasoning, so these stop coming back:

- **Automated rollback or fix suggestions.** The gate informs; humans decide.
- **Function-level impact granularity.** Module level is the unit. Finer
  granularity multiplies the graph without changing the decision it supports.
- **Judging whether a spec honors an obligation.** A rule engine asserts
  coverage. Reviewers judge. See `docs/corpus-review.md`.
- **Collecting production telemetry.** SpecTrace reads git, specs, and test
  results. Observability platforms push SLO status in through
  `update_slo_status` and `POST /api/v1/integrations/slo/status/`; SpecTrace consumes what
  Datadog, groundcover, and New Relic emit and instruments nothing itself. See
  the Scope section of [README.md](README.md).
