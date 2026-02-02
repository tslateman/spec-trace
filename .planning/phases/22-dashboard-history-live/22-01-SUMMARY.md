---
phase: 22
plan: 01
subsystem: dashboard
tags: [flow-runs, templates, filtering, alpine-js]
dependency-graph:
  requires: [21]
  provides: [flow-runs-list, flow-run-detail, history-filtering]
  affects: [22-02]
tech-stack:
  added: []
  patterns: [design-system-templates, alpine-js-expand-collapse]
key-files:
  created:
    - spectrace/templates/admin/requirements/flow_runs.html
    - spectrace/templates/admin/requirements/flow_run_detail.html
  modified:
    - spectrace/requirements/flow_status.py
    - spectrace/requirements/views.py
decisions:
  - id: HIST-FILTERS
    choice: "Status and date range filters in both data layer and view"
    rationale: "Follows existing validation_runs pattern for consistency"
metrics:
  duration: 5m
  completed: 2026-02-02
---

# Phase 22 Plan 01: Flow Runs History List and Detail Views Summary

Flow runs history templates with filtering for status and date range, step timeline with expandable details.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add filtering to flow_runs_view and data layer | b263325 |
| 2 | Create flow_runs.html template | 3516f54 |
| 3 | Create flow_run_detail.html template | 462a9e1 |

## Key Deliverables

### Data Layer Enhancements (Task 1)
- Extended `get_flow_runs_data()` with optional `filters` dict parameter
- Filters: `status` (passed/failed/running), `date_from`, `date_to`
- Added `_build_flow_run_filters()` helper in views.py
- Updated `flow_runs_view()` to parse query params and pass to data layer
- Added `current_filters` to context for template rendering

### Flow Runs List Template (Task 2) - 179 lines
- Extends unfold/layouts/base.html with design system
- Breadcrumbs: Dashboard / Flow Status / {flow_name}
- Summary stats: Total Runs, Passed, Failed, Pass Rate
- Filters card: Status select, Date From/To inputs, Apply/Clear buttons
- Runs table: ID (link), Status badge, Started date, Duration, Steps counts
- Pagination with filter params preserved in links
- Empty state with clear filters action

### Flow Run Detail Template (Task 3) - 276 lines
- Breadcrumbs: Dashboard / Flow Status / {flow_name} / Run #{id}
- Header with run ID, status badge, prev/next navigation
- Summary stats: Total Steps, Passed, Failed, Duration
- Pipeline overview: horizontal bar with color-coded step segments
- Step timeline with Alpine.js expand/collapse:
  - Step name, status badge, duration
  - Details text
  - Error message (red styling)
  - Response status code
  - Response body (nested collapsible)
- Run context JSON (collapsible section)

## Verification

- Template syntax validated via Django Template class
- All 484 tests pass (pytest)
- Templates exceed minimum line requirements (150)
- Follows design system conventions (st-* classes)

## Must-Haves Verified

| ID | Requirement | Status |
|----|-------------|--------|
| HIST-01 | User can see list of all flow runs with status, timestamp, duration | Done |
| HIST-02 | User can filter runs by status and date range | Done |
| HIST-03 | User can drill down to run detail showing step-by-step results | Done |
| HIST-04 | User can see step timing and failure messages in detail view | Done |

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Ready for 22-02 (Live Flow Status) - views and templates are in place for history viewing. Live status polling can be added independently.
