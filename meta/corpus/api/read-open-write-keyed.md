---
id: DEC-API-001
kind: decision
title: Reads need no key, writes need an API key
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: advisory
applies_to:
  tags: [v1]
  paths: ["meta/specs/api-*.md"]
  requirement_ids: ["REQ-SPEC-*", "REQ-TASK-*", "REQ-RSLT-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high, medium]
  - id: auth-tested
    assert: verification_method in [test, both]
---

`GET` under `/api/v1/` needs no API key. Spec content, coverage metrics, drift,
conflicts, and enforcement runs describe the repository, and a dashboard or an
agent reading them leaks nothing a reader of the repository cannot already see.
`POST` needs an API key, because every `POST` under `/api/v1/` mutates state
that a later read reports as fact.

Rejected alternatives: keying every endpoint (turns the public dashboard into a
credential-distribution problem) and keying none (lets an unauthenticated caller
claim tasks and resolve conflicts).

A spec that adds an endpoint MUST place it on the correct side of this line and
MUST say which side. A spec that opens a write or keys a read reopens this
decision and MUST cite it.
