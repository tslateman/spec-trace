---
tags: [spectrace, core, traceability]
priority: high
status: active
risk_level: high
verification_method: test
---

# Core traceability loop

What SpecTrace promises about its own traceability pipeline. Five stages carry a
requirement from a markdown file to a verification status, and every stage below
must hold for the claim on the landing page — "see which requirements are
verified by passing tests" — to mean anything.

## REQ-CORE-000: Traceability loop

SpecTrace connects a written requirement to the tests that verify it and reports
the verification status of every requirement it knows about.

The loop runs in five stages: parse the specs, extract the links, import the
results, compute the status, and validate the links. Each stage is a child of
this requirement. A break at any stage silently degrades every claim SpecTrace
makes downstream, so all five carry `risk_level: high`.

## REQ-CORE-001: Parse specs into requirements

`parse_specs <dir>` reads markdown files with YAML frontmatter and creates or
updates a `Requirement` for each one.

A file carrying `id` in its frontmatter produces one requirement. A file without
`id` produces one requirement per `## REQ-XXX: Title` heading, where the first
heading becomes the root and the rest become its children. A `parent` key names
an explicit parent by external ID. Re-running the command updates existing
requirements by `external_id` rather than duplicating them.

A `risk_level` outside the `RiskLevel` choices fails the parse rather than
defaulting silently.

## REQ-CORE-002: Extract test-requirement links

`extract_links --path <dir>` collects `@pytest.mark.requirement("REQ-XXX")`
markers from a test tree and writes the test-to-requirement mapping as JSON.

Collection runs through pytest in `--collect-only` mode, so a test that fails to
import surfaces as a collection error rather than as a missing link. A test may
declare several requirements; each produces its own link.

## REQ-CORE-003: Import test results

`import_results <junit.xml>` reads a JUnit XML report and records the outcome of
each test against the links extracted in REQ-CORE-002.

A result for a test that no requirement claims is recorded and left unlinked.
Re-importing a report for the same run updates the outcomes rather than
appending duplicates.

## REQ-CORE-004: Compute verification status

Every requirement carries a status derived from its linked test results:
`passing` when linked tests exist and all pass, `failing` when any linked test
fails, and `untested` when no linked test exists.

Status is derived rather than stored by hand. A requirement with no links is
untested, never passing — absence of evidence never reads as verification.

## REQ-CORE-005: Validate links and report drift

`validate_links <links.json>` compares the extracted links against the
requirements in the database and reports drift.

A link naming a requirement that no spec declares is an error. An active
requirement with no linked test is a warning. `--strict` promotes warnings to
errors. `--check-high-risk` adds an error for any critical or high requirement
that has no linked test or has a failing one, and a warning when it has no
linked SLO. The command exits non-zero when errors exist, so a build gates on
it.
