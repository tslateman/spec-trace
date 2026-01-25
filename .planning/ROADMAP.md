# Roadmap: SpecTrace v6

**Milestone:** v6 Impact Analysis & Validation API
**Created:** 2026-01-25
**Phases:** 12-14 (continues from v4 SDK)

## Overview

| Phase | Name | Goal | Requirements |
|-------|------|------|--------------|
| 12 | Impact Analysis Core | Detect spec changes and find affected tests | IMPACT-01, 02, 03 |
| 13 | Impact Analysis UI/CLI | Surface impact analysis in dashboard and CI | IMPACT-04, 05 |
| 14 | Validation API | JSON endpoints for validation run data | API-01, 02, 03 |

## Phase Details

### Phase 12: Impact Analysis Core

**Goal:** Build the core engine that detects spec changes and returns affected tests.

**Requirements:**
- IMPACT-01: Detect changed requirements from git diff
- IMPACT-02: Return list of tests linked to changed requirements
- IMPACT-03: Propagate impact through hierarchy

**Success Criteria:**
1. Given two git refs, service returns list of changed requirement IDs
2. Given a requirement ID, service returns all linked test names
3. When parent requirement changes, child requirements' tests are included
4. Service handles missing refs gracefully with clear error messages

**Approach:**
- Create `ImpactAnalyzer` service class
- Use `git diff` to compare spec files between refs
- Parse changed markdown files to extract requirement IDs
- Query TestRequirementLink for affected tests
- Use treebeard `get_descendants()` for hierarchy traversal

---

### Phase 13: Impact Analysis UI/CLI

**Goal:** Make impact analysis accessible via dashboard and command line.

**Requirements:**
- IMPACT-04: Dashboard view showing impact analysis results
- IMPACT-05: CLI command for CI pipelines

**Success Criteria:**
1. Dashboard has "Impact Analysis" tab/section
2. User can input two git refs and see affected tests
3. CLI command `python manage.py impact_analysis <base> <head>` outputs results
4. CLI supports `--format json` and `--format text` flags
5. Exit code reflects whether changes affect tests (for CI gates)

**Approach:**
- Add dashboard view using existing django-unfold patterns
- Alpine.js for ref input and results display
- Management command wrapping ImpactAnalyzer service
- JSON output for machine consumption, text for humans

---

### Phase 14: Validation API

**Goal:** Expose validation run data via JSON API for custom UI development.

**Requirements:**
- API-01: GET `/api/validation-runs/` — list with filtering
- API-02: GET `/api/validation-runs/<id>/` — detail with steps
- API-03: GET `/api/validation-runs/<id>/steps/` — step detail

**Success Criteria:**
1. List endpoint returns paginated validation runs
2. Filtering works by requirement_id, vendor, status, date range
3. Detail endpoint includes all steps with pass/fail status
4. Steps endpoint includes context JSON and timing
5. Proper error responses for 404, 400 cases

**Approach:**
- Django REST Framework or plain Django JSON views
- Reuse existing InAppValidationRun, InAppValidationResult models
- Follow existing API patterns from health check endpoints
- Add OpenAPI/Swagger docs if time permits

---

## Dependencies

```
Phase 12 (Core)
    └─→ Phase 13 (UI/CLI) — depends on ImpactAnalyzer service

Phase 14 (API) — independent, can run parallel to 12-13
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Git operations slow on large repos | Use `--name-only` flag, limit diff scope |
| Hierarchy traversal expensive | Cache descendant queries, denormalize if needed |
| API performance with many validation runs | Pagination, database indexes |

---
*Roadmap created: 2026-01-25*
