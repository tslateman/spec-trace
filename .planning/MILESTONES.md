# Project Milestones: SpecTrace

## Unreleased — Cloudflare Port (In progress)

**Delivering:** A Worker-hosted API and a React dashboard that CI and agents reach at any hour, fed by the Python CLI running where the repo lives.

**Phases completed:** 0-4 of [plans/cloudflare-port.md](../plans/cloudflare-port.md); phase 5 (cutover) partly done

**Key accomplishments:**

- Worker on Hono, Drizzle, and D1 serving the v1 API at `spectrace.spectrace.workers.dev`, deployed by CI on every merge to main
- `plans/openapi-worker.yaml` frozen as the contract, held by `worker/test/contract.test.ts`
- TaskLedger Durable Object owning task transitions, leases, lease alarms, and the Lore outbox
- React dashboard in `app/` behind GitHub OAuth, reading the Worker over a service binding; PR #2 retired the Worker's own data screens
- CLI pushes specs, links, flows, JUnit results, impact, and drift; `spectrace tasks` and `spectrace linear` run with no Django in the path
- `spectrace tasks run` drains the unclaimed queue, hosted on GitHub Actions every 30 minutes

**Remaining:** stop the Django server. See [ROADMAP.md](../ROADMAP.md) item 1.

**Stats:**

- 190 commits
- 286 files modified
- 2026-08-30 → 2026-09-16

**Git range:** `cfd1af6` → `6d0b149`

**Plan:** [plans/cloudflare-port.md](../plans/cloudflare-port.md)

---

## v11 Corpus Review & Self-Verification (Shipped: 2026-08-30)

**Delivered:** The agent-facing API under `/api/v1/`, a corpus of standards specs are reviewed against, an impact graph that walks code to requirement, and SpecTrace verifying itself.

**Phases completed:** API restructure phases 1-5, then corpus work ad-hoc (outside the GSD workflow)

**Key accomplishments:**

- Every agent-facing endpoint moved under `/api/v1/` with enforcement, impact, and validation-run routes
- Corpus schema, parser, applicability resolver, check evaluator, and the five finding types
- Corpus drift derived from coverage rows and the pinned snapshot; check ids hold across version edits
- Impact graph for cross-project blast radius, plus the Scenario DSL in `spectrace-flows`
- Intent-to-Execution validator with historical tracking
- Task outcomes written to the Lore journal on merge and abandon
- SpecTrace verifying SpecTrace: 23 requirements of its own, gated in CI
- Changelog's Unreleased section generated from the commit log

**Stats:**

- 60 commits
- 186 files modified
- +21,564 lines added
- 6 months (2026-02-27 → 2026-08-30)

**Git range:** `bd320eb` → `04c788e` (tag `v0.11.0`)

---

## v10 Spec as Interface (Shipped: 2026-02-27)

**Delivered:** Specs became the interface agents work from, and coverage became the number that says how much of the interface holds.

**Phases completed:** 1-2 (v10)

**Key accomplishments:**

- `agent_context <task_id>` assembles requirements, `done_when` criteria, dependency tree, test outcomes, and scope boundaries into a markdown document for prompt injection
- `spec_coverage` reports specification, structure, and verification rates
- `detect_integration_risks` finds conflicts across in-flight agent tasks
- Risk scoring on impact analysis and an end-to-end impact demo command
- Conflicts REST API with detection, listing, and resolution endpoints
- OpenAPI spec completed with security schemes and query parameters
- `spectrace` CLI wrapping the Django management commands, and CI running ruff as a blocking gate

**Stats:**

- 14 commits
- 171 files modified
- +11,414 lines added
- 2 days (2026-02-26 → 2026-02-27)

**Git range:** `f7b76cc` → `cd4aa16`

**Tag:** none. `cd4aa16` (docs: Mark v10 milestone complete, 2026-02-27) is the
last commit of the milestone; `bd320eb` opens v11.

**Deferred:** coverage trend snapshots — ROADMAP.md item 2.

---

## v9 Demo & Marketing Polish (Shipped: 2026-02-03)

**Delivered:** Clear value proposition, guided onboarding, and polished demo experience for engineering leads evaluating SpecTrace.

**Phases completed:** 24-28 (5 phases, 7 plans)

**Key accomplishments:**

- Design system enhancement: alternating row colors, dark mode text support for .st-table
- Landing page: PM-focused value prop "See which requirements are verified by passing tests" with 4 feature cards
- Demo data: 7 sample specs with 3-level hierarchy (Epic → Feature → Story), mixed test outcomes
- Driver.js guided tour: 3-step workflow explanation with cross-page sessionStorage trigger
- Getting started guide: 679-line progressive disclosure onboarding with copy-paste code examples

**Stats:**

- 58 commits
- 39 files modified
- +5,700 lines added
- 42,374 lines total (Python + HTML)
- 5 phases, 7 plans
- 1 day (2026-02-03)

**Git range:** `feat(24-01)` → `docs(v9)`

**Archive:** [v9-ROADMAP.md](milestones/v9-ROADMAP.md), [v9-REQUIREMENTS.md](milestones/v9-REQUIREMENTS.md)

---

## v8 Verification Flows (Shipped: 2026-02-02)

**Delivered:** YAML-based verification flows with Admin UI editor, dashboard for run history and live status, and requirement traceability.

**Phases completed:** 19-23 (5 phases, 12 plans)

**Key accomplishments:**

- YAML flow parser with schema validation (parser.py 234 lines)
- Pluggable step executors: api_call, assertion, wait
- Flow execution engine with per-step and per-flow timeouts
- Admin UI flow editor with ruamel.yaml comment preservation
- Dashboard: flow run history with status/date filtering
- Live status view with 5-second Alpine.js polling
- M2M requirement linking with bidirectional admin display

**Stats:**

- 68 files modified
- +11,134 lines added
- 29,759 Python LOC total
- 5 phases, 12 plans
- 1 day (2026-02-02)

**Git range:** `2e9e99f` → `3acb18f`

**Archive:** [v8-ROADMAP.md](milestones/v8-ROADMAP.md), [v8-REQUIREMENTS.md](milestones/v8-REQUIREMENTS.md)

---

## v7 UI Polish & API Documentation (Shipped: 2026-01-25)

**Delivered:** Dark mode consistency, breadcrumb navigation, validation filtering improvements, OpenAPI 3.1 documentation.

**Phases completed:** 15-18 (4 phases)

**Key accomplishments:**

- Dark mode styling across all 10 custom admin templates (311 dark: classes)
- Breadcrumb navigation on detail views
- Loading states for async operations (impact analysis, comparison)
- Date range and requirement ID filters for validation runs
- OpenAPI 3.1 spec generation from msgspec Structs
- Swagger UI at `/api/docs/` with 9 endpoints and 20 schemas

**Stats:**

- 4 commits
- 12 files modified
- 4 phases, 1 day

**Git range:** `dff75a9` → `9757182`

**Archive:** [v7-ROADMAP.md](milestones/v7-ROADMAP.md), [v7-REQUIREMENTS.md](milestones/v7-REQUIREMENTS.md)

---

## v6 Impact Analysis & Validation API (Shipped: 2026-01-25)

**Delivered:** Impact analysis for spec changes, JSON API for validation runs.

**Phases completed:** 12-14 (3 phases)

**Archive:** [v6-ROADMAP.md](milestones/v6-ROADMAP.md), [v6-REQUIREMENTS.md](milestones/v6-REQUIREMENTS.md)

---

## v5 Structured Requirements (Shipped: 2026-01-24)

**Delivered:** FRET-inspired structured requirement fields with enhanced conflict detection, Linear import enrichment, and SLO auto-linking.

**Phases completed:** 5 (ad-hoc, outside GSD workflow)

**Key accomplishments:**

- Optional structured fields: scope, condition, component, timing, response
- Structure completeness scoring with dashboard badge
- Condition-based conflict detection (overlap, timing conflicts, response contradictions)
- Linear import enrichment with best-effort pattern extraction
- SLO auto-linking based on timing field matching
- Component filter and structured fields fieldset in admin

**Stats:**

- 3 new files created
- 6 files modified
- 30 new tests (228 total)
- 5 phases, 1 day

**Git range:** `a3bdbc4` ends the feature work (docs: add v5 Structured
Requirements milestone, 2026-01-24); `c0b1b73` (fix(admin): replace
EmptyFieldListFilter, 2026-01-25) is the last commit before `9ff2af6` opens v6.
The range this file recorded before, `0a47cdf` → `fd13976`, names two commits
that no longer exist in this repository.

**Tag:** none.

**What's next:** v6 — Historical tracking, scheduled validation, alerting

---

## v4 SDK (Shipped: 2026-01-21)

**Delivered:** Production-ready validation SDK with vendor tracking, feature flag correlation, regression detection, examples, and documentation.

**Phases completed:** 8-11 (4 plans total)

**Key accomplishments:**

- ValidationRun context manager with best-effort submission
- Multi-step validation with pass/fail per step (steps, context fields)
- Vendor tracking and feature flag correlation on InAppValidation
- Regression detection (success → failure transitions)
- PMS examples (Opera, Mews) and Mobile Key examples (Ambiance, OpenKey, Vostio)
- Comprehensive SDK docs: README, Integration Guide, Troubleshooting

**Stats:**

- 19 SDK files created
- 12,203 lines of Python (total project)
- 4 phases, 4 plans
- 1 day (2026-01-21)

**Git range:** `dff21cc` → HEAD

**What's next:** v5 — Historical tracking, scheduled validation, alerting

---

## v3 Integration Health Checks (Shipped: 2026-01-22)

**Delivered:** Integration health monitoring with granular diagnostic checks for Linear, REST API endpoints, and dashboard UI showing real-time connection status.

**Phases completed:** 5-7 (8 plans total)

**Key accomplishments:**

- VerificationCheck and TestConnectionResult dataclasses for health diagnostics
- Granular diagnostic checks: configuration, authentication, permissions
- Response sanitization to prevent API key exposure in error messages
- REST API: POST test-connection, GET health with 60s caching
- Alpine.js dashboard widget with color-coded health badges
- Manual "Test Connection" button with loading states

**Stats:**

- 65 commits
- 119 files modified
- 9,354 lines of Python (total)
- 3 phases, 8 plans
- 2 days (2026-01-21 → 2026-01-22)

**Git range:** `9feffb7` → `dff21cc`

**What's next:** v4 — Extended integrations, historical tracking, or automation

---

## v2 Traceability Matrix (Shipped: 2026-01-21)

**Delivered:** Visual grid view showing which tests verify which requirements with filtering and CSV export.

**Phases completed:** 1-4 (v2) (4 plans total)

**Key accomplishments:**

- Paginated matrix grid (requirements × tests) with color-coded cells
- Status, tag, and parent requirement filtering
- CSV export respecting current filters
- Integrated as dashboard tab in django-unfold admin

**Stats:**

- 4 phases, 4 plans
- 1 day (2026-01-21)

**Git range:** `532969a` (docs: create v2 Traceability Matrix milestone) →
`2427557` (docs: mark v2 milestone complete), both 2026-01-21. The range this
file recorded before, `72310b2` → `9feffb7`, names two commits that precede the
`v0.1.0` tag and belong to v1.

**Tag:** none. `63ba019` opens v3.

**What's next:** v3 — Integration health monitoring

---

## v1 MVP (Shipped: 2026-01-21)

**Delivered:** Requirements traceability system connecting product specs to verified tests with Django dashboard showing pass/fail/untested status.

**Phases completed:** 1-4 (6 plans total)

**Key accomplishments:**

- Markdown spec parsing with YAML frontmatter and treebeard hierarchy
- pytest @requirement decorator with extract_links command
- JUnit XML import with verification status computation
- Django-unfold dashboard with metrics banner and hierarchical tree view
- Bidirectional navigation (requirement ↔ tests)
- Link validation command for CI/CD drift detection
- REST API for external system integration
- Linear integration for issue sync

**Stats:**

- 87 files created/modified
- 5,201 lines of Python
- 4 phases, 6 plans
- 3 days from start to ship (2026-01-19 → 2026-01-21)

**Git range:** `3608c1e` (feat: django setup) → `72310b2` (docs: state update)

**What's next:** v2 — Traceability matrix, impact analysis, CI webhooks

---
