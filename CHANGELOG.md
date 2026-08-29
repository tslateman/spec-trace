# Changelog

Milestone history for SpecTrace. Versions match the project's milestone names
(v1–v10), not the package version in `pyproject.toml`. Dates come from git tags
and `.planning/MILESTONES.md`.

Per-milestone detail lives in `.planning/milestones/`. Forward-looking work
lives in [ROADMAP.md](ROADMAP.md).

## [Unreleased]

Six months of work since v10 with no milestone tag. Groups below are the shape
the next release should take.

### Corpus-backed spec review (2026-08-29)

- `corpus review`, `corpus coverage`, `corpus drift`, and `corpus suggest`
  commands, each with `text|json|md` output
- Corpus schema, parser, and immutable entry versions; `parse_corpus` imports
  `corpus/**/*.md`
- Applicability resolver matching entries to requirements by scope rules
- Check evaluator with five finding types: `unaddressed_obligation`,
  `stale_citation`, `orphan_citation`, `unmet_check`, `conflicting_obligations`
- Coverage audit ledger recording every applicable obligation, finding or not
- Drift derived from coverage rows against the pinned corpus snapshot
- Scope-rule widenings proposed from near misses, for a human to accept
- Blocking decision moved to the standard's owner; `--strict` promotes advisory
  findings for one run
- Check ids held stable across corpus version edits
- `risk_level` declarable in spec frontmatter
- Failing-defect canaries covering every finding type
- Seeded corpus domains: billing, identity, platform, security

### Impact graph (2026-03-01)

- Code → requirement mapping through `spectrace-map.yaml`, with `map_init`,
  `map_validate`, and `map_promote` commands
- Git co-change inference for candidate edges
- `code_impact_analysis` command extending impact analysis to code diffs
- `generate_contract` producing `contract.snapshot.json` for cross-project
  surface diffing
- GitHub App and webhook handler at `api/webhooks/github/`, registered only when
  configured

### API v1 (2026-02-27 → 2026-03-01)

- Agent-facing endpoints under `/api/v1/`: tasks, spec context, coverage, drift,
  impact, conflicts, enforcement runs, validation runs
- API contract and naming conventions documented before the restructure
- 61 tests covering v1 endpoints
- Legacy unversioned `/api/` endpoints still served alongside v1

### Other

- Intent-to-Execution validator with historical tracking (`validate_intent`)
- Scenario DSL in `spectrace-flows`
- Agent context overlay: tree hierarchy, drift, Lore integration
- Task outcomes written to the Lore journal on merge and abandon
- `--format md` on `impact` and `verify` for PR comments; emojis and requirement
  titles in CLI output
- Standalone `spectrace` CLI wrapping the Django management commands
- CI pipeline with test and lint gates; ruff pinned to the repo's format version
- 960 ruff errors cleared
- Full-suite pytest collection restored with importlib import mode
- MIT license
- GitNexus index and Claude Code scaffolding

## [v10] — Spec as Interface — 2026-02-27

Specs become the interface agents work from and the standard verification runs
against.

- `agent_context <task_id>` assembles requirements, `done_when` criteria,
  dependency tree, test outcomes, and scope boundaries into a markdown document
  for prompt injection
- `spec_coverage` reports specification, structure, and verification rates
- `detect_integration_risks` finds conflicts across in-flight agent tasks
- Risk scoring on impact analysis
- End-to-end impact demo command

## [v9] — Demo & Marketing Polish — 2026-02-03

- Landing page with the value proposition "See which requirements are verified
  by passing tests" and four feature cards
- Driver.js guided tour, triggered across pages through sessionStorage
- Getting-started guide with copy-paste examples
- Seven sample specs, three levels deep, with mixed test outcomes
- `.st-table` alternating rows and dark-mode text
- QA Ecosystem page explaining integrations

## [v8] — Verification Flows — 2026-02-02

- YAML flow parser with schema validation
- Pluggable step executors: `api_call`, `assertion`, `wait`, with per-step and
  per-flow timeouts
- Admin flow editor preserving comments through ruamel.yaml
- Flow run history with status and date filtering
- Live status view polling every five seconds
- Many-to-many requirement linking with bidirectional admin display
- `spectrace-flows` extracted as a standalone package

## [v7] — UI Polish & API Documentation — 2026-01-25

- Dark mode across all ten custom admin templates
- Breadcrumbs on detail views and loading states on async operations
- Date-range and requirement-ID filters for validation runs, persisted in the URL
- OpenAPI 3.1 spec generated from msgspec Structs, Swagger UI at `/api/docs/`

## [v6] — Impact Analysis & Validation API — 2026-01-25

- `ImpactAnalyzer` deriving affected tests from a git diff of spec files
- Parent requirement changes propagate to child tests
- Impact analysis dashboard at `/admin/impact-analysis/`
- `impact_analysis <base> <head>` for CI, with JSON and text output
- Validation run REST endpoints

## [v5] — Structured Requirements — 2026-01-24

- FRET-inspired optional fields: scope, condition, component, timing, response
- Conflict detection on condition overlap, timing, and response contradiction
- Structure completeness scoring with a dashboard badge
- SLO auto-linking by timing field
- Structured field extraction during Linear import

## [v4] — SDK — 2026-01-21

- `ValidationRun` context manager with best-effort submission
- Multi-step validation with per-step pass/fail
- Vendor tracking and feature flag correlation
- Regression detection on success → failure transitions
- PMS (Opera, Mews) and mobile key (Ambiance, OpenKey, Vostio) examples
- SDK README, integration guide, and troubleshooting guide

## [v3] — Integration Health Checks — 2026-01-22

- `VerificationCheck` and `TestConnectionResult` diagnostics
- Configuration, authentication, and permission checks for Linear
- Response sanitization keeping API keys out of error messages
- `POST test-connection` and `GET health` with 60-second caching
- Dashboard health widget with a manual Test Connection button

## [v2] — Traceability Matrix — 2026-01-21

- Paginated requirements × tests grid with color-coded cells
- Status, tag, and parent requirement filters
- CSV export respecting the active filters

## [v1] — MVP — 2026-01-21

- Markdown spec parsing with YAML frontmatter into a treebeard hierarchy
- `@pytest.mark.requirement("REQ-XXX")` and the `extract_links` command
- JUnit XML import and passing/failing/untested status computation
- django-unfold dashboard with a metrics banner and hierarchical tree
- Bidirectional navigation between requirements and tests
- `validate_links` for CI drift detection
- REST API and Linear issue sync
