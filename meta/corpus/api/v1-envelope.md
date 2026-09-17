---
id: STD-API-001
kind: standard
title: Every v1 response carries data or a coded error
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: blocking
applies_to:
  tags: [v1]
  paths: ["meta/specs/api-*.md"]
  requirement_ids: ["REQ-SPEC-*", "REQ-TASK-*", "REQ-RSLT-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high, medium]
  - id: envelope-tested
    assert: verification_method in [test, both]
---

Every `/api/v1/` response is the same shape: a `data` object on success, an
`error` object carrying a machine-readable `code` on failure. An endpoint
returns one or the other and never both.

A spec that adds or changes a `/api/v1/` endpoint MUST name the `code` each
failure path returns. Returning a bare list, returning `200` with an error body,
or reporting a failure as an empty `data` object violates this standard, because
each of them makes a client read the HTTP status to learn what happened.
