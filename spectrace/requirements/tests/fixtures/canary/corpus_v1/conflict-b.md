---
id: CANARY-STD-CONFLICT-B
kind: standard
title: Planted defect — component must not be storage
version: 1
status: active
effective: 2026-01-01
owner: canary
enforcement: advisory
applies_to:
  tags: [canary-fixture]
checks:
  - id: component-is-not-storage
    assert: component != storage
---

The other half of the planted contradiction. No requirement can satisfy this
entry and `CANARY-STD-CONFLICT-A` at once.
