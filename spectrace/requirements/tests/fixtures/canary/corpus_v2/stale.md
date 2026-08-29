---
id: CANARY-STD-STALE
kind: standard
title: Planted defect — version 2, the version that applies
version: 2
status: active
effective: 2026-06-01
owner: canary
enforcement: advisory
applies_to:
  tags: [canary-fixture]
checks:
  - id: spec-status-active
    assert: status == active
---

Version 2 keeps every check id version 1 defined, so the bump is a lawful one.
Importing `corpus_v1/` and then this directory leaves both versions in the
snapshot: the matcher must apply version 2 alone and write one coverage row.
