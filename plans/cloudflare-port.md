# Cloudflare Port

Move the spec-trace server to Cloudflare Workers in TypeScript. The Python CLI
stays, runs where the repo lives, and pushes what it reads from disk and git.

**Accountable:** Mainstay (contract stability), Marshal (cutover)

**Status:** Phases 0–4 shipped; phase 5 partly done. The Worker serves
production at `spectrace.spectrace.workers.dev`, CI deploys it on merge to
main, and the push job feeds it specs, links, flows, and JUnit results.
Pushing impact and drift reports from CI and stopping the Django server
remain.

**Last measured:** 2026-09-09 — see Success Criteria below.

## Scope

| The Port Is                                           | The Port Isn't                               |
| ----------------------------------------------------- | -------------------------------------------- |
| A Worker that stores, serves, and renders spec-trace  | A Python Worker or a Django-on-Containers    |
| The v1 API contract reimplemented on D1               | New features beyond what v1 serves today     |
| The CLI as the only reader of specs, tests, and git   | A second parser in TypeScript                |
| The custom screens (matrix, coverage, impact, runs)   | Django ModelAdmin or any generic CRUD tables |
| Task claims and leases in a Durable Object            | Multi-tenant auth or a tenant model          |
| Lore outcomes drained by the CLI from a Worker outbox | The Worker calling Lore                      |

## Problem

The server runs only where the repo is checked out. Request handlers read
`specs/` and `flows/` from disk (`matrix.py:271`, `flow_editor.py:24`,
`api_v1.py:251`) and shell out to `git` (`views.py:47`, `api_v1.py:284`). The
database is a SQLite file beside the code. Agents and CI can reach the API only
while the Mac that holds the checkout is awake.

Workers have no filesystem, no subprocess, and no Django. The Python server
cannot move there as it stands, and Containers keep an ephemeral disk that
resets on sleep, so the SQLite file dies there too.

## Goal

A Worker-hosted API and UI that CI and agents reach at any hour, fed by the
Python CLI running where the repo lives.

## Success Criteria

Measured 2026-09-09 against the deployed Worker and a Django server holding
the same facts. Each line says met, unmet, or what it now measures instead.

- **Met.** A GitHub Actions job runs `spectrace push --url $SPECTRACE_URL` and
  the pushed requirements appear in the matrix screen on the next load.
  `worker.yml` runs it after every deploy; D1 holds 32 requirements and 117
  links.
- **Met.** Two agents call `POST /api/v1/tasks/{id}/claim` in the same
  millisecond and exactly one succeeds. Proven by `worker/test/ledger.test.ts`.
- **Met.** A claimed task whose lease lapses returns to `unclaimed` without a
  human or a cron job within one minute of expiry. Proven by the alarm tests in
  `worker/test/ledger.test.ts`.
- **Met for the route set, partly for response shapes.** `worker/test/contract.test.ts`
  reads `plans/openapi-worker.yaml` and fails when the Worker's registered
  `/api/v1` operations differ from the contract's in either direction, which
  is the check that would have caught the test-run ingest path missing from
  the contract for a month. The same file validates the 200 body of the four
  list endpoints against their declared schemas; the other 30 operations have
  no schema check yet.
- **Met for `status`, close for `context`.** Django and the Worker return
  byte-identical JSON for `GET /specs/{id}/status/` on 32 of 32 requirements,
  and for `GET /specs/{id}/context` on 24 of 32. The eight that differ are
  orphan demo links in the local database whose test files no longer exist; the
  Worker omits them correctly.
- **Unproven.** Every merged or abandoned task outcome reaches Lore's journal
  after one run of `spectrace lore sync`. The Worker half is covered by the
  outbox tests; no task has been merged through production, so the outbox is
  empty and the CLI half has never run end to end.
- **Met.** Deploy is `git push`; CI runs `wrangler deploy`; no host to log into.
- **Met, by a route this line did not anticipate.** No one-shot migration ran;
  `spectrace push` fills D1, and re-measuring on 2026-09-16 with
  `scripts/cutover/compare_django_d1.py` finds nothing left to migrate. Of 31
  shared tables, 25 hold equal counts, D1 leads on 6, and Django leads on none.
  Every requirement `external_id` and every test nodeid in `db.sqlite3` is
  already in D1. The gap the 2026-09-09 measurement recorded closed from both
  ends: `spectrace push --slos` (PR #11) and `--corpus` (PR #12) gave two of
  those four table groups a push path, and `db.sqlite3` itself was rebuilt from
  migrations on 2026-09-16, so it now holds 154 rows against D1's 62,536 and
  carries no corpus entry, intent validation result, agent task, or flow run at
  all. `backfill_django_to_d1.py --dry-run` plans 0 inserts across its 7 tables.

  Re-measuring surfaced one constraint worth carrying forward. Requirement
  primary keys differ between the two stores for 27 of 33 requirements —
  `REQ-BILL-002` is id 7 in Django and id 11 in D1 — so any row ever copied out
  of `db.sqlite3` must resolve its foreign keys through `external_id`. The
  backfill does, and `spectrace/tests/test_backfill_django_to_d1.py` holds it
  to that. A verbatim id copy attaches history to the wrong requirement without
  erroring.

## Architecture

Three parts, one direction of flow: the CLI pushes, the Worker stores and
serves, humans and agents read.

| Part                            | Runtime                     | Owns                                                               |
| ------------------------------- | --------------------------- | ------------------------------------------------------------------ |
| `spectrace` CLI (kept, Python)  | Dev machines, CI            | Parsing specs, corpus, flows, JUnit; git diff and co-change; drift |
| Worker (new, TypeScript)        | Cloudflare Workers          | v1 API, screens, D1 schema, auth, rate limits                      |
| `TaskLedger` (new, Durable Obj) | One per `SPECTRACE_PROJECT` | Task transitions, leases, lease alarms, the Lore outbox            |

### Worker

- **Hono** for routing and server-rendered JSX screens.
- **Drizzle** on **D1**. D1 is SQLite, so the 25-model schema moves with its
  dialect intact. Treebeard's materialized path stays a string column with
  prefix queries.
- **Workers Static Assets** for CSS and JS.
- **Auth:** `SPECTRACE_API_KEY` as a Worker secret, checked on every `/api/`
  route. Today the key guards three endpoints and everything else is open
  (`docs/api-contract.md:49`); on a public host everything is guarded.
  Cloudflare Access in front of the screens.
- **Rate limits:** a Cloudflare rate-limit rule replaces `django-ratelimit`.
- **Migration:** a one-shot script dumps `db.sqlite3`, drops the tables owned
  by non-goals, and loads D1 with `wrangler d1 execute`.

### TaskLedger

`services/agent_tasks.py` (692 lines) holds the state machine: `claim_task`,
`start_task`, `submit_for_review`, `review_task`, `merge_task`,
`release_task`, `expire_stale_leases`. It ports as a Durable Object because a
DO is single-writer by construction, which makes claims atomic without a
transaction dance, and its alarm API fires at `lease_expires` exactly, which
retires `expire_leases` as a scheduled command.

Terminal transitions (`merged`, `abandoned`) append to an `outcomes` table in
D1. That table is the Lore outbox.

### CLI

New or changed commands:

| Command                      | Replaces                                          | Pushes to                              |
| ---------------------------- | ------------------------------------------------- | -------------------------------------- |
| `spectrace push`             | `parse_specs`, `import_test_links`, `parse_flows` | `PUT /api/v1/specs/`                   |
| `spectrace results push`     | `import_results`, `import_inapp_validations`      | `POST /api/v1/results/`                |
| `spectrace impact --push`    | `impact_analysis` on the server                   | `POST /api/v1/results/impact/`         |
| `spectrace drift --push`     | `detect_drift` on the server                      | `POST /api/v1/results/drift/`          |
| `spectrace demo load <name>` | The `admin-*-load-demo` views                     | `PUT /api/v1/specs/`, `POST /results/` |
| `spectrace lore sync`        | `lore_bridge.notify_lore()` inside `merge_task`   | Drains `GET /api/v1/tasks/outcomes`    |

The CLI keeps its parsers, `ImpactAnalyzer`, `GitCoChangeAnalyzer`, and
`detect_all_drift` unchanged. It gains an HTTP client; `spectrace_client`
already has one.

## Contract Changes

Added to v1:

| Endpoint                            | Purpose                                                |
| ----------------------------------- | ------------------------------------------------------ |
| `PUT /api/v1/specs/`                | Bulk upsert of the requirement tree, links, and flows  |
| `POST /api/v1/results/impact/`      | Store an impact report; `GET /specs/impact/` serves it |
| `POST /api/v1/results/drift/`       | Store a drift report; `GET /specs/drift/` serves it    |
| `GET /api/v1/tasks/outcomes?since=` | Read the Lore outbox                                   |
| `POST /api/v1/tasks/outcomes/ack`   | Mark outcomes drained                                  |

Changed semantics: `GET /specs/impact/` and `GET /specs/drift/` return the last
pushed report instead of computing one. Their response shapes stay.

Removed: the unversioned `/api/*` routes in `api.py` (766 lines), which the v1
restructure superseded.

## Screens

Ported from `views.py`, rendered by Hono JSX against D1:

landing · matrix and export · vendor coverage · impact analysis · high-risk
dashboard · requirement detail · validation runs (list, detail, steps, compare)
· flow status (list, live, runs, run detail) · about · spec syntax help ·
getting started · overview · QA ecosystem · demo hub

Dropped:

- **Flow editor** (`flow_editor_list_view`, `flow_editor_view`,
  `flow_sync_to_db_view`). It writes YAML into `flows/` on the server's disk.
  Flows live in the repo and get edited there; `spectrace push` syncs them.
- **ModelAdmin** (19 registrations, 3 inlines, 0 actions). Raw rows are
  reachable through the CLI and the D1 console.
- **Load-demo views.** `spectrace demo load` pushes the same data.

## Non-goals

Stated so the port has an edge:

- GitHub App: webhooks, JWT auth, PR impact comments (`github_app.py`,
  `WebhookEvent`). GitHub Actions running the CLI covers CI without an App.
- Linear import, report, test-connection, and health endpoints.
- The `spectrace-flows` runtime on the server. `run_flow` runs from the CLI and
  pushes results.
- Python Workers. Beta, no D1 ORM, and the parsers would leave the server
  anyway, so language continuity buys nothing.
- Containers. The port exists so nothing needs a disk.
- Multi-tenancy. One `SPECTRACE_PROJECT`, one `TaskLedger`, one API key.

## Phases

Each phase ships on its own and names what proves it done.

### 0. Freeze the contract

Write `plans/openapi-worker.yaml`: `plans/openapi.yaml` minus the non-goal
paths plus the five added endpoints. Regenerate `spectrace_client` against it.

**Done when:** the CLI's client tests pass against a mock of the new document.

**Shipped.** The document drifts from the Worker, though: `POST
/results/test-runs/` ran in production for a month before the contract named
it. Phase 5's contract test is what stops that recurring.

### 1. Store and read

Drizzle schema for the 23 surviving models, the migration script, and every
`GET` in the contract.

**Done when:** a script diffs `GET /specs/{id}/context` and `GET /specs/{id}/status`
from Django and the Worker for every migrated requirement and reports zero
differences.

**Shipped, the diff run by hand.** `status` matches on 32 of 32, `context` on
24 of 32, the rest orphan demo rows local to Django. No script owns this — it
was run ad hoc on 2026-09-09 and will rot. Write it, or fold it into the
phase-5 contract test.

### 2. Push

`PUT /api/v1/specs/`, `POST /results/`, `/results/impact/`, `/results/drift/`,
and the CLI commands that feed them.

**Done when:** a fresh D1 filled only by `spectrace push` and
`spectrace results push` from this repo matches the phase-1 migrated database
row for row.

**Partly shipped.** Specs, links, flows, and JUnit results all push, and
`results push` now routes XML to `POST /results/test-runs/`. Four groups still
have no push path and sit empty in D1: corpus entries and snapshots, intent
validation results, agent tasks and agents, and flow runs and steps. Impact and
drift accept pushes but nothing in CI sends them, so the dashboard's impact
and drift views serve nothing.

### 3. TaskLedger

The Durable Object, its alarm, the outbox, and the task endpoints.

**Done when:** the concurrent-claim test and the lease-expiry test pass in the
Worker suite, and `spectrace lore sync` writes a journal entry for a task
merged through the API.

**Shipped in the Worker, unproven end to end.** Both tests pass. No task has
been merged through production, so the outbox is empty and `spectrace lore
sync` has never drained a real outcome.

### 4. Screens

The ported list above.

**Done when:** every screen renders against the migrated data and a screenshot
of each lands in the PR.

**Shipped, then retired.** Two screens read data that was wrong until
2026-09-09: high-risk counted zero passing and zero failing tests, and
requirement detail showed every test as unknown, because nothing refreshed a
link's `last_status`. PR #2 deleted the screens on 2026-09-10 once the React
dashboard in `app/` replaced them; the Worker keeps only the public demo page
and the admin redirects.

### 5. Cutover

Access in front, the API key on every route, `wrangler deploy` in CI, the
GitHub Actions job pushing on merge to main.

**Done when:** every success criterion above is green and the Django server is
stopped.

**In progress.** Done: the API key guards every `/api/` route, CI runs
`wrangler deploy` on merge to main, and the push job feeds production.
Remaining:

- Push impact and drift reports from CI so the dashboard's views carry data.
- Stop the Django server.

## Size

The non-test Python server is ~30k lines; templates are 29 files, ~11k lines.
The CLI and client (~2k lines) stay. The parsers, analyzers, and drift
detection (~2.5k lines) stay. `api.py`, `github_app.py`, `admin.py`, the
Linear commands, the flow editor, and the demo loaders (~3.5k lines) are
dropped. What ports is the models, `api_v1.py`, `agent_tasks.py`, the
conflict and corpus services, the surviving views, and their templates.

## Risks

- **Parity of computed reads.** Coverage, conflicts, and corpus views compute in
  the request. The phase-1 diff script is the guard; extend it to every `GET`
  that carries numbers.
- **Worker CPU limits.** Paid Workers allow 30 s CPU per request. The current
  dataset is 831 KB; nothing here approaches the limit, but the coverage and
  matrix queries should page rather than load whole tables.
- **Two schemas drifting.** The CLI's push payload and D1's schema must agree.
  The contract document in phase 0 owns that agreement; changes go there first.
- **Cloudflare surface churn.** Static Assets, DO alarms, and D1 are GA;
  nothing in this design leans on a beta product.

## Open Questions

- **Settled: the React dashboard.** Phase 4 shipped server-rendered Hono JSX
  screens, and the dashboard in `app/` replaced them; PR #2 deleted the
  screens on 2026-09-10.
- Whether `IntentValidationResult` and the review models (`SpecReview`,
  `ReviewCoverage`, `ReviewFinding`) get pushed from the CLI or written by the
  Worker. They are written by management commands today. Still open, and now
  measurable: those tables hold rows in `db.sqlite3` and zero in D1. Corpus
  entries, agent tasks, and flow runs sit in the same position.
- Whether the outbox needs an `ack` at all. `since=` with the CLI storing a
  cursor may be enough. Both exist and both are tested; no production task has
  exercised either.
