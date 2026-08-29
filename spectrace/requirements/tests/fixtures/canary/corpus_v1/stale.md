---
id: CANARY-STD-STALE
kind: standard
title: Planted defect — version 1, the version the canary spec cites
version: 1
status: active
effective: 2026-01-01
owner: canary
enforcement: advisory
applies_to:
  tags: [canary-fixture]
checks:
  - id: spec-status-active
    assert: status == active
---

Version 1 of the entry the canary spec cites. `corpus_v2/stale.md` bumps it to
version 2, so the citation goes stale and the snapshot holds two versions of one
entry.
