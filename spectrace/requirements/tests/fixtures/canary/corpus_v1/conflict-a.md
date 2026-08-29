---
id: CANARY-STD-CONFLICT-A
kind: standard
title: Planted defect — component must be storage
version: 1
status: active
effective: 2026-01-01
owner: canary
enforcement: advisory
applies_to:
  tags: [canary-fixture]
checks:
  - id: component-is-storage
    assert: component == storage
---

Half of the planted contradiction. `CANARY-STD-CONFLICT-B` asserts the opposite
on the same field, and both apply to REQ-CANARY-001, so the review must raise
`conflicting_obligations` against `CANARY-STD-CONFLICT-A#component-is-storage`.
