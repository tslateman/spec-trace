---
tags: [spectrace, api, v1, tasks]
priority: high
status: active
risk_level: medium
verification_method: test
---

# API v1 — agent surface

`/api/v1/tasks/` is the contract agents work against: find work, take it, report
the outcome. Three endpoints, each a child of REQ-TASK-000.

## REQ-TASK-000: Agent task surface

`/api/v1/tasks/` lets an agent discover available work, claim it exclusively,
and report completion.

Every response follows the v1 envelope: a `data` object on success, an `error`
object carrying a machine-readable `code` on failure.

## REQ-TASK-001: List available tasks

`GET /api/v1/tasks/` returns agent tasks, newest first, capped by a `limit`
query parameter that defaults to 50.

## REQ-TASK-002: Claim a task

`POST /api/v1/tasks/{task_id}/claim` assigns a task to the claiming agent and
takes a lease on it.

A task already claimed by another agent rejects the second claim rather than
transferring ownership. Claiming a task that does not exist returns an error,
not an empty success.

## REQ-TASK-003: Complete a task

`POST /api/v1/tasks/{task_id}/complete` records the outcome of a claimed task,
including the `done_when` results the agent reports.

Completing a task the caller has not claimed is rejected.
