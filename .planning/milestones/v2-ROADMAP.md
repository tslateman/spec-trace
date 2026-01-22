# Roadmap: v2 Traceability Matrix

## Overview

v2 delivers a traceability matrix view — a paginated grid showing requirements vs. tests with color-coded cells indicating verification status. The matrix integrates as a tab in the existing django-unfold dashboard.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (e.g., 1.1): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Matrix Data Layer** - Query optimization and data structure for grid rendering
- [x] **Phase 2: Matrix View** - Grid template with paginated requirements and scrollable tests
- [ ] **Phase 3: Filtering & Navigation** - Status/tag filters, cell drill-down, URL state
- [ ] **Phase 4: Export & Polish** - CSV export, responsive design, performance tuning

## Phase Details

### Phase 1: Matrix Data Layer
**Goal:** Efficient query layer to fetch requirement-test relationships for matrix rendering
**Depends on:** v1 complete
**Requirements:** MATRIX-01 (partial), MATRIX-02 (data)
**Success Criteria** (what must be TRUE):
  1. Single query fetches all requirement-test links with status for a page of requirements
  2. Query handles 100 requirements × 500 tests in < 500ms
  3. Data structure supports sparse representation (only store linked cells)
  4. Test results include pass/fail/untested status
**Plans:** TBD

### Phase 2: Matrix View
**Goal:** Render the traceability matrix grid in the django-unfold dashboard
**Depends on:** Phase 1
**Requirements:** MATRIX-01, MATRIX-02, MATRIX-04
**Success Criteria** (what must be TRUE):
  1. Matrix displays as a tab in the dashboard
  2. Requirements shown as rows with pagination (25 per page default)
  3. Tests shown as columns with horizontal scroll
  4. Cells color-coded: green (pass), red (fail), yellow (untested), gray (no link)
  5. Legend explains color meanings
**Plans:** TBD

### Phase 3: Filtering & Navigation
**Goal:** Enable filtering and drill-down for focused analysis
**Depends on:** Phase 2
**Requirements:** MATRIX-03, MATRIX-05
**Success Criteria** (what must be TRUE):
  1. Filter dropdown for requirement status (passing/failing/untested)
  2. Filter dropdown for requirement tags
  3. Filter for parent requirement (show subtree)
  4. Clicking a cell shows popover with requirement/test details
  5. Popover includes links to detail pages
  6. Filter state persisted in URL query params
**Plans:** TBD

### Phase 4: Export & Polish
**Goal:** Export capability and production-ready polish
**Depends on:** Phase 3
**Requirements:** MATRIX-06
**Success Criteria** (what must be TRUE):
  1. Export button generates CSV of current view
  2. CSV respects active filters
  3. Matrix is responsive (usable on tablet)
  4. Loading states for pagination and filtering
  5. Performance target: < 2s load for 100 requirements
**Plans:** TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Matrix Data Layer | 1/1 | Complete | 2026-01-21 |
| 2. Matrix View | 1/1 | Complete | 2026-01-21 |
| 3. Filtering & Navigation | 0/? | Not Started | - |
| 4. Export & Polish | 0/? | Not Started | - |

---
*Roadmap created: 2026-01-21*
*Milestone: v2 Traceability Matrix*
