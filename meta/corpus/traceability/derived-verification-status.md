---
id: COM-CORE-001
kind: commitment
title: Verification status is derived from linked tests, never asserted
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: blocking
applies_to:
  tags: [traceability]
  paths: ["meta/specs/core-loop.md"]
  requirement_ids: ["REQ-CORE-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: derivation-tested
    assert: verification_method in [test, both]
  - id: stage-active
    assert: status != draft
---

The landing page tells a reader they can see which requirements passing tests
verify. That claim rests on one rule: a requirement's verification status comes
from its linked test results and from nothing else. `passing` means linked tests
exist and all of them pass. `failing` means one of them fails. `untested` means
no link exists.

A requirement with no linked test is `untested`, never `passing`. Absence of
evidence never reads as verification, and no field, flag, or override may set a
status by hand.

A spec that adds a stage to the loop — parse, extract, import, compute,
validate — MUST say how a break at that stage surfaces, because a stage that
fails quietly degrades every claim downstream of it.
