---
id: DEC-BILL-002
kind: decision
title: Event stream is the metering source of truth
version: 1
status: active
supersedes: DEC-BILL-001@1
effective: 2026-01-05
owner: billing
applies_to:
  tags: [billing, finance, subscriptions]
  components: [metering, api]
  paths: ["specs/billing/**"]
  requirement_ids: ["REQ-BILL-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: metering-tested
    assert: verification_method in [test, both]
  - id: no-batch-dependency
    assert: component != nightly_batch
---

The metered usage event stream is the billable record. Rollups derive from the
stream and MUST be reproducible by replaying it.

A spec that reads usage counters MUST read them from the stream or from a
rollup that declares its stream offset. Reading the nightly batch table directly
violates this decision.
