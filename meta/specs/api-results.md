---
tags: [spectrace, api, v1, results]
priority: high
status: active
risk_level: medium
verification_method: test
---

# API v1 — evidence surface

`/api/v1/results/` carries enforcement evidence and conflict state. Reads need
no key because the data is operational; writes need an API key because they
mutate it. Six endpoints, each a child of REQ-RSLT-000.

## REQ-RSLT-000: Evidence surface

`/api/v1/results/` exposes enforcement runs and detected conflicts, and accepts
the writes that resolve them.

GET endpoints require no authentication. POST endpoints require an API key.

## REQ-RSLT-001: List conflicts

`GET /api/v1/results/conflicts/` returns detected conflicts, filterable by
confidence.

## REQ-RSLT-002: Detect conflicts

`POST /api/v1/results/conflicts/detect` runs conflict detection across active
agent tasks and records what it finds.

Detection names overlapping requirements, dependency chain violations, and
`scope_in` path overlap between tasks in flight.

## REQ-RSLT-003: Get one conflict

`GET /api/v1/results/conflicts/{conflict_id}` returns a single conflict with the
tasks and requirements involved.

## REQ-RSLT-004: Resolve a conflict

`POST /api/v1/results/conflicts/{conflict_id}/resolve` marks a conflict resolved
and records who resolved it and when.

Resolving a conflict that is already resolved does not overwrite the original
resolution.

## REQ-RSLT-005: Report the latest enforcement run

`GET /api/v1/results/enforcement-runs/latest/` returns the most recent
enforcement run matching the supplied filters.

## REQ-RSLT-006: Diff two enforcement runs

`GET /api/v1/results/enforcement-runs/{run_id}/diff/` returns what changed
between a run and its predecessor: checks that started failing, checks that
recovered, and checks that appeared or disappeared.

A regression — a check that passed in the predecessor and fails in this run —
is named as such rather than left for the caller to derive.
