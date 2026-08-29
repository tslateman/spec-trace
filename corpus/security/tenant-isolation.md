---
id: STD-SEC-001
kind: standard
title: Tenant data isolation
version: 3
status: active
supersedes: null
effective: 2026-01-15
owner: platform
applies_to:
  tags: [platform, security]
  components: [api, storage]
  paths: ["specs/platform/**", "specs/workspaces/**"]
  requirement_ids: ["REQ-PLAT-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: has-isolation-test
    assert: verification_method in [test, both]
---

Every query that reads tenant-scoped data MUST filter by tenant at the
persistence layer. Application-level filtering does not satisfy this standard.

A spec that touches tenant-scoped storage, API surfaces, or workspace boundaries
MUST state which layer enforces the filter and name the test that proves a
cross-tenant read fails.
