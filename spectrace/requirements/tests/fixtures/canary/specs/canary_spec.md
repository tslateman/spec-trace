---
id: REQ-CANARY-001
title: Canary requirement carrying one planted defect per finding type
status: active
priority: high
tags: [canary-fixture]
component: storage
verification_method: test
complies_with: [CANARY-STD-STALE@1, CANARY-STD-ORPHAN@1, CANARY-STD-UNMET@1]
---

# Canary requirement

This requirement exists to fail. Every planted defect the canary asserts is a
property of this frontmatter read against `fixtures/canary/corpus_v1/` and
`fixtures/canary/corpus_v2/`:

- It omits `CANARY-STD-UNADDRESSED`, which applies to it.
- It cites `CANARY-STD-STALE@1` while version 2 applies.
- It cites `CANARY-STD-ORPHAN@1`, which applies to nothing.
- It states no `timing`, which `CANARY-STD-UNMET#timing-stated` demands.
- Its `component` satisfies `CANARY-STD-CONFLICT-A` and contradicts
  `CANARY-STD-CONFLICT-B`, which both apply.

Editing this file without editing `test_corpus_canary.py` breaks the canary.
