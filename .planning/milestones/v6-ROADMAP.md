# Milestone Archive: SpecTrace v6 — Impact Analysis & Validation API

**Shipped:** 2026-01-25
**Phases:** 12-14
**Duration:** 1 day
**Commits:** 6
**Files Changed:** 18
**Lines:** +3,216 / -24
**Tests:** 29 passing

## Summary

v6 delivers impact analysis for spec changes and a JSON API for validation runs. When requirements change in git, the system now identifies affected tests. Custom UIs can consume validation data via REST endpoints.

## Key Accomplishments

1. **Impact Analysis Core** — ImpactAnalyzer service detects changed requirements from git diff, returns affected tests, propagates through hierarchy
2. **Dashboard View** — Impact analysis accessible from admin dashboard with git ref inputs
3. **CLI Command** — `manage.py impact_analysis <base> <head>` for CI pipelines with JSON/text output
4. **Validation API** — Full REST API for validation runs: list, detail, and step-level endpoints
5. **Test Coverage** — 29 tests covering analyzer, CLI command, and API endpoints

## Phase Details

### Phase 12: Impact Analysis Core

**Goal:** Build the core engine that detects spec changes and returns affected tests.

**Requirements Delivered:**
- IMPACT-01: Detect changed requirements from git diff
- IMPACT-02: Return list of tests linked to changed requirements
- IMPACT-03: Propagate impact through hierarchy

**Implementation:**
- Created `ImpactAnalyzer` service class in `services/impact_analyzer.py`
- Uses `git diff --name-only` to compare spec files between refs
- Parses changed markdown files to extract requirement IDs
- Queries TestRequirementLink for affected tests
- Uses treebeard `get_descendants()` for hierarchy traversal

**Tests:** 11 tests in `test_impact_analyzer.py`

---

### Phase 13: Impact Analysis UI/CLI

**Goal:** Make impact analysis accessible via dashboard and command line.

**Requirements Delivered:**
- IMPACT-04: Dashboard view showing impact analysis results
- IMPACT-05: CLI command for CI pipelines

**Implementation:**
- Dashboard view at `/admin/impact-analysis/` with Alpine.js for ref input
- Management command `impact_analysis` with `--format json|text` flag
- Exit code reflects whether changes affect tests (for CI gates)

**Tests:** 7 tests in `test_impact_analysis_command.py`

---

### Phase 14: Validation API

**Goal:** Expose validation run data via JSON API for custom UI development.

**Requirements Delivered:**
- API-01: GET `/api/validation-runs/` — list with filtering
- API-02: GET `/api/validation-runs/<id>/` — detail with steps
- API-03: GET `/api/validation-runs/<id>/steps/` — step detail

**Implementation:**
- Created `api.py` with Django JSON views (no DRF dependency)
- Pagination, filtering by requirement, vendor, status, date range
- Proper error responses for 404, 400 cases

**Tests:** 11 tests in `test_validation_api.py`

---

## Requirements Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMPACT-01 | Phase 12 | Complete |
| IMPACT-02 | Phase 12 | Complete |
| IMPACT-03 | Phase 12 | Complete |
| IMPACT-04 | Phase 13 | Complete |
| IMPACT-05 | Phase 13 | Complete |
| API-01 | Phase 14 | Complete |
| API-02 | Phase 14 | Complete |
| API-03 | Phase 14 | Complete |

**Coverage:** 8/8 requirements delivered (100%)

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Plain Django JSON views (no DRF) | Avoid extra dependency for simple endpoints |
| git diff via subprocess | Direct shell command simpler than GitPython |
| Hierarchy propagation via treebeard | Efficient descendant queries built-in |
| CLI exit codes for CI | Zero = no impact, non-zero = tests affected |

## Deferred to v7+

- CI-01: Webhooks receive test results from CI pipeline
- CI-02: Real-time dashboard updates as CI runs complete
- ANLYT-01: Historical coverage trends chart

---
*Archived: 2026-01-25*
