---
tags: [spectrace, api, v1, specs]
priority: high
status: active
risk_level: medium
verification_method: test
---

# API v1 — contract surface

`/api/v1/specs/` answers "what does the spec say?" Read-heavy endpoints that
agents and dashboards call to understand requirements, coverage, drift, and
blast radius. Five endpoints, each a child of REQ-SPEC-000.

## REQ-SPEC-000: Spec contract surface

`/api/v1/specs/` exposes requirement content and derived metrics over HTTP
without an API key, since spec state is non-sensitive.

## REQ-SPEC-001: Assemble spec context

`GET /api/v1/specs/{external_id}/context` returns the requirement, its
`done_when` criteria, its dependency tree, linked test outcomes, and scope
boundaries as one document an agent can inject into a prompt.

This is the HTTP form of the `agent_context` command and returns the same
material.

## REQ-SPEC-002: Report coverage metrics

`GET /api/v1/specs/coverage/` returns the specification rate (non-draft over
total), the structure rate (average FRET completeness), and the verification
rate (passing over total).

The three rates come from a single database aggregate, so a caller never sees
figures computed against different snapshots of the data.

## REQ-SPEC-003: Report spec drift

`GET /api/v1/specs/drift/` names stale links and orphaned requirements, taking
an optional `specs_dir` to check a tree other than the configured one.

## REQ-SPEC-004: Analyze spec impact

`GET /api/v1/specs/impact/` returns the tests and child requirements a change to
a given `spec_id` puts at risk.

Impact propagates down the requirement hierarchy: a change to a parent reaches
the tests linked to its children.

## REQ-SPEC-005: Report requirement status

`GET /api/v1/specs/{external_id}/status/` returns one requirement's verification
status and the linked test results behind it.

An unknown `external_id` returns an error carrying that code, never a default
status.
