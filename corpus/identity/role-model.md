---
id: DEC-IAM-002
kind: decision
title: Three built-in roles, custom roles gated to enterprise
version: 1
status: active
supersedes: null
effective: 2026-02-12
owner: identity
enforcement: advisory
applies_to:
  tags: [permissions, identity]
  components: [auth, api]
  paths: ["specs/identity/**", "specs/workspaces/**"]
  requirement_ids: ["REQ-IAM-002", "REQ-WRK-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: permission-checks-tested
    assert: verification_method in [test, both]
---

Tenant Admin, Member, and Viewer are the only built-in roles. Custom roles are
an enterprise-tier capability composed from the same granular permission set.

A spec that introduces a fourth built-in role, or that grants a capability to a
role outside this model, MUST cite this decision and state why the role model
cannot express the requirement.
