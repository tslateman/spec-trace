---
id: STD-API-002
kind: standard
title: A repeated write updates in place and never reassigns ownership
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: blocking
applies_to:
  paths:
    [
      "meta/specs/api-tasks.md",
      "meta/specs/api-results.md",
      "meta/specs/core-loop.md",
    ]
  requirement_ids: ["REQ-TASK-*", "REQ-RSLT-*", "REQ-CORE-001", "REQ-CORE-003"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high, medium]
  - id: replay-tested
    assert: verification_method in [test, both]
---

Running a write twice leaves the same state as running it once. `parse_specs`
updates a `Requirement` by `external_id` rather than creating a second one,
`import_results` updates the outcomes of a re-imported run rather than appending
them, and `parse_corpus` records a version it already holds as unchanged.

Where a write carries ownership, the second attempt is rejected rather than
absorbed. A task already claimed rejects the second claim instead of
transferring the lease, completing a task the caller has not claimed is
rejected, and resolving an already-resolved conflict keeps the first resolution
and its resolver.

A spec that adds a write MUST state what a replay of it does, and MUST name the
test that runs it twice.
