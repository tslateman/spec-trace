---
id: STD-SEC-002
kind: standard
title: Audit log retention and immutability
version: 1
status: active
supersedes: null
effective: 2026-02-01
owner: security
applies_to:
  tags: [compliance, security]
  components: [audit, storage]
  paths: ["specs/platform/**"]
  requirement_ids: ["REQ-PLAT-002"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high, medium]
  - id: retention-stated
    assert: timing is set
  - id: audit-verified
    assert: verification_method in [test, both]
---

Audit records MUST be append-only and retained for seven years. No application
code path may update or delete an audit row.

A spec that emits audit events MUST state the retention window and MUST NOT
route audit writes through the same connection pool that serves tenant reads.
