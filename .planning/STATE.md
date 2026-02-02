# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-02)

**Core value:** PMs can see, at any moment, which requirements are verified by passing tests
**Current focus:** v8 Verification Flows

## Current Position

Milestone: v8 Verification Flows — IN PROGRESS
Phase: 20 (Flow Execution Engine) — IN PROGRESS
Status: **Plan 20-01 complete, ready for 20-02**
Last activity: 2026-02-02 — Completed 20-01-PLAN.md (step executors)

Progress: ██░░░ 1.5/5 phases (Phases 19-23)

## v8 Summary

Build a verification flow system where:
- Flows are defined in YAML files (source of truth)
- Admin UI reads/writes YAML files for editing
- Dashboard shows flow run history and live status
- Flows link to requirements for traceability

See: .planning/milestones/v8-ROADMAP.md
See: .planning/v8/REQUIREMENTS.md

## Phase 20 Progress

**Plan 20-01 complete:**
- Step executors module (api_call, assertion, wait)
- STEP_EXECUTORS registry with execute_step dispatcher
- Engine extended with step_timeout/flow_timeout parameters
- Metadata filtering (skips _metadata entries)
- 27 new tests, 65 total tests passing

**Commits:**
- 404f0bb: feat(20-01): add step executors for api_call, assertion, wait
- 37cb2fb: feat(20-01): extend engine with step dispatcher and timeout handling
- fa27012: test(20-01): add comprehensive executor tests

## Phase 19 Completion

**Plans executed:** 3/3 (including gap closure plan 03)
**Commits:** 11 total
**Tests:** 30 new tests, all passing
**Verification:** 7/7 must-haves verified

**Key deliverables:**
- YAMLFlowParser class (234 lines) with schema validation
- Extended FlowDef/FlowStepDef with type, config, requirements, source_file fields
- parse_flows management command with --dry-run and --clear flags (accepts files or directories)
- sync_yaml_flows_to_db function for database syncing
- 2 example YAML flows in flows/ directory

## Milestone History

| Milestone | Shipped | Phases | Summary |
|-----------|---------|--------|---------|
| v8 Flows | In progress | 19-23 | YAML-based verification flows with Admin UI and dashboard |
| v7 UI Polish | 2026-01-25 | 15-18 | Dark mode, breadcrumbs, filtering, OpenAPI docs |
| v6 Impact | 2026-01-25 | 12-14 | Impact analysis and validation API (29 tests) |
| v4 SDK | 2026-01-21 | 8-11 | In-app validation SDK with vendor tracking, feature flags, examples, docs |
| v3 Health | 2026-01-22 | 5-7 | Linear integration health checks with dashboard UI |
| v2 Matrix | 2026-01-21 | 1-4 (v2) | Traceability matrix view |
| v1 MVP | 2026-01-21 | 1-4 (v1) | Spec parsing, test linking, verification dashboard |

See: .planning/MILESTONES.md

## Post-v4 Work (Outside GSD)

Two features implemented outside the GSD workflow (ad-hoc development):

1. **Linear traceability** (0a47cdf): Test-requirement link tracking with Linear issue sync
2. **Structured requirement fields** (71763a9): FRET-inspired fields (scope, condition, component, timing, response) with:
   - Enhanced conflict detection (condition overlap, timing, response contradictions)
   - Linear import enrichment (pattern extraction from issue descriptions)
   - SLO auto-linking by timing field
   - Structure completeness scoring in dashboard

## Accumulated Context

### Key Decisions (v8)

- YAML as source of truth (not database)
- Admin UI writes directly to YAML files
- Dashboard: flow run history + live status (no requirement coverage view)
- Full stack scope (backend + UI)
- Handler field required only for type=handler steps (19-01)
- Return None for non-flow YAML, raise FlowParseError for malformed (19-01)
- Store metadata (source_file, requirements) in steps JSON as _metadata key (19-02)
- clear_existing deletes only flows matching provided names, not all YAML-sourced flows (19-02)
- Signal-based timeout using SIGALRM for POSIX, skip on Windows (20-01)
- Executor registry pattern: STEP_EXECUTORS dict maps type -> function (20-01)
- last_response context key for passing data between api_call and assertion steps (20-01)
- Response body truncation at 1000 chars to prevent DB bloat (20-01)

### Blockers/Concerns

None.

### Next Steps

Execute plan 20-02: run_flow management command + integration tests.

## Phase 20 Plan Summary

**Plans:** 2 plans in 2 waves
**Requirements:** EXEC-01 through EXEC-06

| Plan | Wave | Status | Objective |
|------|------|--------|-----------|
| 20-01 | 1 | COMPLETE | Step executors (api_call, assertion, wait) + engine timeout handling |
| 20-02 | 2 | PENDING | run_flow management command + integration tests |

## Session Continuity

Last session: 2026-02-02
Stopped at: Completed 20-01-PLAN.md
Resume file: None
