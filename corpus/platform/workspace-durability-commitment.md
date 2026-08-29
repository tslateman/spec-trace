---
id: COM-PLAT-001
kind: commitment
title: Workspace durability and recovery window
version: 2
status: active
supersedes: null
effective: 2026-02-20
owner: platform
applies_to:
  tags: [core, workspaces, collaboration]
  components: [storage, api]
  paths: ["specs/workspaces/**", "specs/platform/**"]
  requirement_ids: ["REQ-WRK-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: recovery-window-stated
    assert: timing is set
  - id: durability-verified
    assert: verification_status != failing
---

We commit to customers that a deleted workspace is recoverable for 30 days and
that no workspace content is destroyed before that window closes.

A spec that deletes, archives, or migrates workspace content MUST state the
recovery window it honors and MUST name the test that proves content survives
the documented period.
