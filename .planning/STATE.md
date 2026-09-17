# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** PMs can see, at any moment, which requirements are verified by passing tests
**Current focus:** Finishing the Cloudflare cutover — see [plans/cloudflare-port.md](../plans/cloudflare-port.md)

## Current Position

Milestone: Unreleased — Cloudflare Port, after v0.11.0 (Corpus Review & Self-Verification)
Phase: Cloudflare port, phase 5 (cutover)
Plan: [plans/cloudflare-port.md](../plans/cloudflare-port.md)
Status: The Worker serves production at `spectrace.spectrace.workers.dev` and CI
deploys it on merge to main. CI pushes specs, links, flows, JUnit results, and
since 2026-09-16 impact and drift reports, so the dashboard reads what the
Worker holds. `spectrace tasks` and `spectrace linear` run with no Django in the
path, and `spectrace tasks run` drains the queue from GitHub Actions every 30
minutes. Stopping the Django server is what remains; see ROADMAP item 1.
Live coverage numbers live in the generated block of
[docs/current-state.md](../docs/current-state.md), which `spectrace consolidate`
rewrites from the Worker.
Last activity: 2026-09-15 — Linear moved to the CLI (#10); `tasks context` reads
the Worker

Progress: Phases 0–4 shipped, phase 5 partly done.

## Milestone History

| Milestone                             | Shipped     | Phases    | Summary                                                         |
| ------------------------------------- | ----------- | --------- | --------------------------------------------------------------- |
| Cloudflare Port                       | in progress | 0-5       | Worker, D1, TaskLedger, dashboard; the CLI pushes what it reads |
| v11 Corpus Review & Self-Verification | 2026-08-30  | ad-hoc    | `/api/v1/`, corpus review, impact graph, SpecTrace on itself    |
| v10 Spec as Interface                 | 2026-02-27  | 1-2 (v10) | Agent context, spec coverage, integration risk detection        |
| v9 Demo & Marketing                   | 2026-02-03  | 24-28     | Value prop, guided tour, onboarding guide                       |
| v8 Flows                              | 2026-02-02  | 19-23     | YAML-based verification flows with Admin UI and dashboard       |
| v7 UI Polish                          | 2026-01-25  | 15-18     | Dark mode, breadcrumbs, filtering, OpenAPI docs                 |
| v6 Impact                             | 2026-01-25  | 12-14     | Impact analysis and validation API                              |
| v4 SDK                                | 2026-01-21  | 8-11      | In-app validation SDK                                           |
| v3 Health                             | 2026-01-22  | 5-7       | Linear integration health checks                                |
| v2 Matrix                             | 2026-01-21  | 1-4 (v2)  | Traceability matrix view                                        |
| v1 MVP                                | 2026-01-21  | 1-4 (v1)  | Spec parsing, test linking, verification dashboard              |

## v11 Summary

**Goal:** Give agents one API to work against and give specs a standard to be reviewed against

**Delivered:**

- Every agent-facing endpoint under `/api/v1/`, with enforcement, impact, and validation-run routes
- Corpus schema, parser, applicability resolver, and check evaluator with five finding types
- Corpus drift derived from coverage rows and the pinned snapshot
- Impact graph for cross-project blast radius, and the Scenario DSL in `spectrace-flows`
- Intent-to-Execution validator with historical tracking
- SpecTrace verifying SpecTrace: 23 requirements of its own, gated in CI

**Stats:** 60 commits, 186 files, +21,564 lines, 6 months (2026-02-27 → 2026-08-30)

## Accumulated Context

### Decisions

Decisions logged in PROJECT.md Key Decisions table.

Cloudflare port key decisions:

- The CLI parses specs, tests, and git; the Worker stores and serves what the CLI pushes
- `plans/openapi-worker.yaml` is the frozen contract, and `worker/test/contract.test.ts` fails when the Worker and the contract disagree
- Task claims and leases live in a Durable Object, which is single-writer by construction
- The React dashboard in `app/` owns every data screen; the Worker keeps one public demo page
- Linear runs from the CLI; no server holds the token
- Code impact diffs each project across its own ref pair

### Blockers/Concerns

- The Django server still runs. Stopping it is the last step of phase 5.
- Corpus entries and snapshots, flow runs and steps, externally created agent
  tasks, and SLOs have no push path and sit empty in D1.
- No task has merged through production, so `spectrace lore sync` has never
  drained a real outcome.

## Session Continuity

Last session: 2026-09-15
Stopped at: Linear moved to the CLI as `spectrace linear`, and `tasks context`
joined the commands that read the Worker.
Resume file: none — [ROADMAP.md](../ROADMAP.md) carries what comes next.
