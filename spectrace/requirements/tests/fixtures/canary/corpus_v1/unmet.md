---
id: CANARY-STD-UNMET
kind: standard
title: Planted defect — structural check the canary spec fails
version: 1
status: active
effective: 2026-01-01
owner: canary
enforcement: advisory
applies_to:
  tags: [canary-fixture]
checks:
  - id: timing-stated
    assert: timing is set
---

The canary spec cites this entry and states no `timing`, so the review must
raise `unmet_check` against `CANARY-STD-UNMET#timing-stated`.
