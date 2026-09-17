---
id: STD-CORE-001
kind: standard
title: Bad input fails loudly, never as a silent default
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: blocking
applies_to:
  paths: ["meta/specs/core-loop.md", "meta/specs/api-*.md"]
  requirement_ids: ["REQ-CORE-*", "REQ-SPEC-*", "REQ-TASK-*", "REQ-RSLT-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high, medium]
  - id: rejection-tested
    assert: verification_method in [test, both]
---

Input SpecTrace cannot honor raises where it arrives. A `risk_level` outside the
`RiskLevel` choices fails the parse and names the file. A test that fails to
import surfaces as a collection error rather than as a missing link. An unknown
`external_id` returns an error carrying that code rather than a default status.
Claiming a task that does not exist returns an error rather than an empty
success.

A default that stands in for rejected input converts a bug into a wrong answer
that reads as a right one, and traceability reported from wrong answers is worse
than no report.

A spec that reads a value a caller supplies MUST say what an unacceptable value
does, and the answer MUST name an error rather than a fallback.
