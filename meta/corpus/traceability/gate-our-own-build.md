---
id: COM-CORE-002
kind: commitment
title: SpecTrace gates its own build on its own traceability
version: 1
status: active
supersedes: null
effective: 2026-09-15
owner: spectrace
enforcement: blocking
applies_to:
  paths: ["meta/specs/core-loop.md"]
  requirement_ids: ["REQ-CORE-000", "REQ-CORE-005"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: gate-tested
    assert: verification_method in [test, both]
  - id: gate-not-regressed
    assert: verification_status != failing
---

We run SpecTrace on SpecTrace. CI parses `specs/` and `meta/specs/`, extracts
the `@pytest.mark.requirement` links, and runs `validate_links --check-high-risk`,
which errors on any critical or high requirement with no linked test or a
failing one. The command exits non-zero, so the build stops.

A tool that asked others to prove their requirements and skipped its own would
be selling a claim it had not tested. Every SpecTrace requirement carrying
`risk_level: high` therefore carries a linked test, and the gate stays blocking.

A spec that raises a SpecTrace requirement to `high` or `critical` MUST link the
test before it merges. Loosening the gate — dropping `--check-high-risk`, or
letting the job continue on error — reopens this commitment.
