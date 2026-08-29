---
id: CANARY-STD-STALE
kind: standard
title: Planted defect — version 3 renames a check id and declares nothing
version: 3
status: active
effective: 2026-07-01
owner: canary
enforcement: advisory
applies_to:
  tags: [canary-fixture]
checks:
  - id: spec-is-active
    assert: status == active
---

Version 3 renames `spec-status-active` to `spec-is-active` with no
`renamed_from` and no `retired_checks`. Findings cite
`CANARY-STD-STALE#spec-status-active` without a version, so the parser must
reject this file.
