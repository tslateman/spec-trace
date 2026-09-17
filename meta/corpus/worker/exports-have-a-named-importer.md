---
id: STD-WORKER-001
kind: standard
title: Every exported Worker symbol has a named importer
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: advisory
applies_to:
  tags: [worker, screens]
  paths: ["meta/specs/prune-screen-exports.md"]
  requirement_ids: ["REQ-WORKER-*"]
checks:
  - id: export-audit-tested
    assert: verification_method in [test, both]
  - id: spec-active
    assert: status != draft
---

Every symbol a module under `worker/src/` exports is imported by name from at
least one other module under `worker/src/`. An export nothing imports is dead
code that typechecks, and the Worker accumulated 38 screens' worth of it before
PR #2.

The audit resolves each `import { … } from "<relative path>"` to a file and
matches the names against that file's exports, so it fails for the right reason.
Matching words instead of import specifiers passes or fails by accident. Reading
the source text rather than a module namespace is what makes `export type` and
`export interface` visible.

This standard carries no `risk_level` check. Pruning dead code is low risk by
construction, and a check demanding otherwise would be red forever.
