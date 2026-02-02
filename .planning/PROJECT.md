# SpecTrace

## What This Is

A requirements traceability system that connects product specs to verified code. Specs live in the codebase as markdown files with YAML frontmatter, pytest tests are annotated with requirement IDs via `@pytest.mark.requirement("REQ-XXX")`, and a Django dashboard shows PMs, engineers, and QA which requirements are actually verified by passing tests.

## Core Value

PMs can see, at any moment, which requirements are verified by passing tests — eliminating the gap between "what we think we built" and "what we actually built."

## Current Milestone

Planning next milestone.

## What's Shipped

### v8 Verification Flows (Shipped: 2026-02-02)

- **YAML flow parser:** Parse flow definitions from YAML files with schema validation
- **Step executors:** Pluggable api_call, assertion, wait step types with timeout handling
- **Admin UI flow editor:** Visual editor with ruamel.yaml comment preservation
- **Dashboard views:** Flow run history with filtering + live status with 5s polling
- **Requirement linking:** M2M between flows and requirements with bidirectional admin display

### v7 UI Polish & API Documentation (Shipped: 2026-01-25)

- **Dark mode consistency:** All 10 custom admin templates with proper dark: classes (311 occurrences)
- **Breadcrumb navigation:** Detail views have clear navigation paths
- **Loading states:** Impact analysis and comparison views show spinners
- **Validation filtering:** Date range and requirement ID filters with URL persistence
- **OpenAPI documentation:** Full API spec at `/api/openapi.json` with Swagger UI at `/api/docs/`

### v6 Impact Analysis & Validation API (Shipped: 2026-01-25)

- **Impact Analysis Core:** ImpactAnalyzer service detects changed requirements from git diff, returns affected tests
- **Hierarchy propagation:** Parent requirement changes include child tests in impact
- **Dashboard view:** Impact analysis accessible at `/admin/impact-analysis/` with git ref inputs
- **CLI command:** `manage.py impact_analysis <base> <head>` for CI pipelines with JSON/text output
- **Validation API:** REST endpoints for validation runs (list, detail, steps) at `/api/validation-runs/`
- **Test coverage:** 29 tests covering analyzer, CLI command, and API endpoints

### v5 Structured Requirements (Shipped: 2026-01-24)

- **Structured requirement fields:** FRET-inspired optional fields (scope, condition, component, timing, response) for formal requirement specification
- **Enhanced conflict detection:** Condition overlap, timing conflicts, and response contradiction detection based on structured fields
- **Linear import enrichment:** Best-effort extraction of structured fields from issue descriptions
- **SLO auto-linking:** Auto-link SLOs to requirements based on timing field matching
- **Structure completeness scoring:** Dashboard shows percentage of structured fields populated per requirement
- **Linear traceability:** Test-requirement link tracking with Linear issue sync

### v4 SDK (Shipped: 2026-01-22)

- **SDK Core:** ValidationRun context manager, ValidationStep, ValidationStatus
- **Vendor tracking:** Group validations by integration vendor (Opera, Mews, etc.)
- **Feature flags:** Auto-extract from Django settings, env vars, model fields
- **Step reporting:** Granular pass/fail per validation step
- **Regression detection:** Automatic detection of passing → failing transitions
- **Examples:** PMS (Opera, Mews), Mobile Key (Ambiance, OpenKey, Vostio)
- **Documentation:** README, Integration Guide, Troubleshooting Guide

### v3 Integration Health Checks (Shipped: 2026-01-22)

- **Health diagnostics:** VerificationCheck and TestConnectionResult dataclasses
- **Granular checks:** Configuration, authentication, permissions for Linear
- **REST API:** POST test-connection, GET health with 60s caching
- **Dashboard:** Alpine.js widget with color-coded badges and Test Connection button
- **Security:** Response sanitization to prevent API key exposure

### v2 Traceability Matrix (Shipped: 2026-01-21)

- **Matrix view:** Paginated grid (requirements × tests) with color-coded cells
- **Filtering:** Status, tags, parent requirement filters
- **Export:** CSV export respecting filters
- **Dashboard tab:** Integrated in django-unfold admin

### v1 MVP (Shipped: 2026-01-21)

**Lines of code:** 5,201 Python
**Tech stack:** Django 5.2, django-treebeard, django-unfold, pytest, junitparser

- **Spec parsing:** Markdown files with YAML frontmatter → hierarchical requirements
- **Test linking:** `@pytest.mark.requirement("REQ-XXX")` decorator → JSON links
- **Status computation:** JUnit XML import → passing/failing/untested per requirement
- **Dashboard:** Metrics banner + hierarchical tree with status indicators
- **Navigation:** Bidirectional (requirement ↔ tests)
- **Validation:** CI command to detect drift between tests and requirements
- **Extended:** REST API, Linear integration, in-app validation, SLO support

## Requirements

### Validated

- ✓ SPEC-01: Spec parsing from markdown — v1
- ✓ SPEC-02: Unique IDs (REQ-XXX format) — v1
- ✓ SPEC-03: Hierarchical requirements — v1
- ✓ SPEC-04: Tag filtering — v1
- ✓ SPEC-05: Git versioning — v1
- ✓ LINK-01: pytest @requirement decorator — v1
- ✓ LINK-02: Multiple tests → one requirement — v1
- ✓ LINK-03: One test → multiple requirements — v1
- ✓ LINK-04: extract_links command — v1
- ✓ VERIFY-01: Verification status (passing/failing/untested) — v1
- ✓ VERIFY-02: Status derivation from test results — v1
- ✓ VERIFY-03: JUnit XML import — v1
- ✓ DASH-01: Hierarchical dashboard — v1
- ✓ DASH-02: Summary metrics — v1
- ✓ DASH-04: Coverage gap highlighting — v1
- ✓ DASH-05: Search by ID/text/status/tag — v1
- ✓ DASH-06: Filter by category/tag — v1
- ✓ NAV-01: Requirement → linked tests — v1
- ✓ NAV-02: Test → linked requirements — v1
- ✓ HEALTH-01: Connection testing endpoints for integrations — v3
- ✓ HEALTH-02: Granular diagnostic checks (config, auth, permissions) — v3
- ✓ HEALTH-03: Each check includes name, passed, details, timestamp — v3
- ✓ HEALTH-04: Failed checks include error_message and response details — v3
- ✓ HEALTH-05: Individual checks aggregate into overall status — v3
- ✓ HEALTH-06: GET endpoint returns cached status without triggering check — v3
- ✓ DASH-07: Dashboard shows Linear integration health status — v3
- ✓ DASH-08: Dashboard shows last-checked timestamp — v3
- ✓ DASH-09: User can trigger health check from dashboard — v3
- ✓ SDK-01: ValidationRun context manager with best-effort submission — v4
- ✓ SDK-02: Multi-step validation with pass/fail per step — v4
- ✓ SDK-03: Vendor tracking on InAppValidation model — v4
- ✓ SDK-04: Feature flag extraction from Django/env/model — v4
- ✓ SDK-05: Regression detection (success → failure) — v4
- ✓ SDK-06: Vendor coverage dashboard with pass rates — v4
- ✓ SDK-07: PMS validation examples (Opera, Mews) — v4
- ✓ SDK-08: Mobile key validation examples (Ambiance, OpenKey, Vostio) — v4
- ✓ SDK-09: Django admin action factory — v4
- ✓ SDK-10: REST API endpoint examples — v4
- ✓ SDK-11: SDK README with API reference — v4
- ✓ SDK-12: Integration guide with checklists — v4
- ✓ SDK-13: Troubleshooting guide — v4
- ✓ STRUCT-01: Optional structured fields (scope, condition, component, timing, response) — post-v4
- ✓ STRUCT-02: Structure completeness scoring with dashboard badge — post-v4
- ✓ STRUCT-03: Condition-based conflict detection (overlap, timing, response) — post-v4
- ✓ STRUCT-04: Linear import enrichment with pattern extraction — post-v4
- ✓ STRUCT-05: SLO auto-linking by timing field — post-v4
- ✓ TRACE-01: Linear issue traceability and conflict detection — post-v4

### Validated (v7)

- ✓ FILTER-01: Date range filter on validation runs list — v7
- ✓ FILTER-02: Filter by specific requirement ID — v7
- ✓ FILTER-03: Persist filters across navigation (URL params) — v7
- ✓ DOCS-01: Generate OpenAPI spec from msgspec Structs — v7
- ✓ DOCS-02: Serve OpenAPI JSON at `/api/openapi.json` — v7
- ✓ DOCS-03: Add Swagger UI at `/api/docs/` — v7
- ✓ DARK-01: Fix validation runs list page dark mode — v7
- ✓ DARK-02: Fix validation run detail page dark mode — v7
- ✓ DARK-03: Fix validation run comparison page dark mode — v7
- ✓ DARK-04: Fix impact analysis page dark mode — v7
- ✓ NAV-01: Add breadcrumb navigation to detail views — v7
- ✓ NAV-02: Add "back to list" links on detail pages — v7
- ✓ LOAD-01: Add loading spinner for impact analysis form — v7
- ✓ LOAD-02: Add loading state for validation run comparison — v7

### Validated (v6)

- ✓ IMPACT-01: Detect changed requirements from git diff — v6
- ✓ IMPACT-02: Show affected tests for changed requirements — v6
- ✓ IMPACT-03: Include hierarchy (parent change → child tests) — v6
- ✓ IMPACT-04: Dashboard view for impact analysis — v6
- ✓ IMPACT-05: CLI command for CI integration — v6
- ✓ API-01: JSON endpoint for InAppValidationRun list with filtering — v6
- ✓ API-02: JSON endpoint for InAppValidationRun detail — v6
- ✓ API-03: JSON endpoint for validation steps and results — v6

### Validated (v8)

- ✓ FLOW-01: Parse flow definitions from YAML files — v8
- ✓ FLOW-02: YAML schema supports id, title, steps[], requirement links — v8
- ✓ FLOW-03: Each step has name, type (api_call, assertion, wait), config — v8
- ✓ FLOW-04: Admin UI reads existing YAML files as editable form — v8
- ✓ FLOW-05: Admin UI writes changes back to YAML files — v8
- ✓ FLOW-06: Validate YAML syntax and schema on save — v8
- ✓ EXEC-01: Flow runner executes steps sequentially — v8
- ✓ EXEC-02: Record VerificationFlowRun with pass/fail status — v8
- ✓ EXEC-03: Record VerificationFlowStep results for each step — v8
- ✓ EXEC-04: Support step types: api_call, assertion, wait — v8
- ✓ EXEC-05: CLI command: manage.py run_flow <flow_id> — v8
- ✓ EXEC-06: Timeout handling per step and per flow — v8
- ✓ HIST-01: List all flow runs with status, timestamp, duration — v8
- ✓ HIST-02: Filter runs by flow, date range, status — v8
- ✓ HIST-03: Drill down to run detail showing step-by-step results — v8
- ✓ HIST-04: Show step timing and failure messages — v8
- ✓ LIVE-01: Real-time view of currently executing flows — v8
- ✓ LIVE-02: Show current step being executed — v8
- ✓ LIVE-03: Auto-refresh or polling updates — v8
- ✓ LIVE-04: Visual progress indicator — v8
- ✓ LINK-01: Flows can specify linked requirement IDs in YAML — v8
- ✓ LINK-02: Requirement detail page shows linked flows — v8
- ✓ LINK-03: Flow dashboard shows which requirements each flow verifies — v8

### Future (v9+)

- [ ] CI-01: Webhooks receive test results from CI pipeline
- [ ] CI-02: Real-time dashboard updates as CI runs complete
- [ ] ANLYT-01: Historical coverage trends chart

### Out of Scope

- Built-in test execution — consume results, don't run tests
- Electronic signatures — not targeting compliance
- Complex approval workflows — enterprise overhead
- Real-time collaborative editing — git handles this
- Multi-repo aggregation — single repo focus
- AI requirement generation — requirements need human judgment

## Context

**Problem solved:**
- Specs scattered across Slack, Notion, Linear, meetings → specs in codebase
- No way to answer "is requirement X implemented and working?" → dashboard shows status
- Tests may verify wrong behavior → explicit requirement linking

**Tech choices:**
- Django for dashboard (Python ecosystem, team familiarity)
- treebeard for hierarchy (efficient tree queries without recursive SQL)
- django-unfold for modern UI (Tailwind-based admin)
- pytest markers for test linking (native to existing workflow)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Specs in codebase, not Notion | Version control, no drift, reviewable changes | ✓ Good |
| Markdown format | Human-readable, easy for PMs to write/review | ✓ Good |
| pytest annotations | Native to existing test workflow | ✓ Good |
| Django for dashboard | Stays in Python ecosystem, team familiarity | ✓ Good |
| django-treebeard for hierarchy | Efficient tree queries, no recursive SQL | ✓ Good |
| Denormalized verification_status | Fast dashboard reads, recompute on import | ✓ Good |
| Deferred traceability matrix | Bidirectional navigation sufficient for v1 | ✓ Shipped in v2 |
| Dataclasses for health checks | Separate domain logic from persistence (Repository pattern) | ✓ Good |
| Synchronous health checks | Avoid Django async/timeout deadlocks | ✓ Good |
| Cached health results | Respect Linear API rate limits (5K req/hr) | ✓ Good |
| 60s cache TTL | Balance between rate limiting and freshness | ✓ Good |
| Response sanitization | Prevent API key exposure in error diagnostics | ✓ Good |
| Alpine.js for dashboard widget | Bundled with django-unfold, no extra dependencies | ✓ Good |
| FRET-inspired structured fields | NASA FRET approach without formal verification overhead | ✓ Good |
| Optional structured fields | All new fields optional - teams adopt when valuable | ✓ Good |
| Best-effort pattern extraction | Parse Linear descriptions without strict grammar | ✓ Good |
| Bundled SDK (spectrace_client) | No separate package, always in sync with SpecTrace | ✓ Good |
| Context manager pattern | Clean resource management, automatic submission | ✓ Good |
| Best-effort submission | Never break user code if SpecTrace down | ✓ Good |
| Multi-source flag extraction | Support Django settings, env vars, model fields | ✓ Good |
| 5-step PMS / 3-step mobile key | Consistent validation granularity | ✓ Good |
| YAML as flow source of truth | Version control, reviewable flow changes | ✓ Good |
| ruamel.yaml for round-trip | Preserve YAML comments during editing | ✓ Good |
| Executor registry pattern | Pluggable step types without engine changes | ✓ Good |
| Signal-based timeouts | POSIX SIGALRM for per-step/per-flow timeout | ✓ Good |
| M2M linking by external_id | Decouple flow sync from requirement existence | ✓ Good |
| 5-second polling for live status | Balance responsiveness with server load | ✓ Good |

---
*Last updated: 2026-02-02 after v8 milestone completion*
