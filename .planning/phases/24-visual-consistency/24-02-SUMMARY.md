---
phase: 24-visual-consistency
plan: 02
subsystem: ui
tags: [css, dark-mode, design-system, tables]

# Dependency graph
requires:
  - phase: 24-01
    provides: Enhanced .st-table with alternating rows and dark mode text
provides:
  - All demo page tables use design system .st-table class
  - Dark mode works correctly on all demo pages (VIS-03)
  - Redundant custom CSS removed (115+ lines)
affects: [25-landing-page, 26-demo-data]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use html.dark selector for dark mode (not .dark)"
    - "Tables use st-table class for consistent styling"
    - "Keep semantic-specific CSS (like .change-improved) separate from base table styles"

key-files:
  created: []
  modified:
    - spectrace/templates/admin/requirements/validation_run_compare.html
    - spectrace/templates/admin/requirements/qa_ecosystem.html
    - spectrace/templates/admin/requirements/spectrace_overview.html

key-decisions:
  - "Keep change-* status classes as inline styles (semantic colors for this specific page)"
  - "Keep summary-table class for last-row accent highlight on QA ecosystem page"
  - "Keep demo-matrix-table class for column alignment and req-id styling"
  - "Integration tables in cards stay unchanged (special styling needs per research)"

patterns-established:
  - "Combine st-table with additional classes for page-specific enhancements"

# Metrics
duration: 8min
completed: 2026-02-03
---

# Phase 24 Plan 02: Table Migration Summary

**Migrated 3 templates to use .st-table, removing 115+ lines of redundant CSS while ensuring dark mode works on all demo pages**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-03T16:05:00Z
- **Completed:** 2026-02-03T16:13:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- validation_run_compare.html now includes design system and uses st-table
- qa_ecosystem.html tables migrated to st-table (component table + summary table)
- spectrace_overview.html demo matrix table migrated to st-table
- Dark mode selector pattern corrected (.dark -> html.dark)
- 115+ lines of redundant custom table CSS removed

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate validation_run_compare.html** - `a02025c` (feat)
2. **Task 2: Migrate qa_ecosystem.html tables** - `d717a71` (feat)
3. **Task 3: Migrate spectrace_overview.html table** - `76930c9` (feat)

## Files Created/Modified
- `spectrace/templates/admin/requirements/validation_run_compare.html` - Added design system include, st-table class, html.dark selectors
- `spectrace/templates/admin/requirements/qa_ecosystem.html` - Replaced component-table and summary-table CSS with st-table
- `spectrace/templates/admin/requirements/spectrace_overview.html` - Replaced demo-matrix-table CSS with st-table

## Decisions Made
1. **Keep semantic status classes** - The change-* classes (improved/regressed/etc) in validation_run_compare.html are semantic for this specific page, so kept as inline styles with corrected html.dark selectors
2. **Preserve page-specific enhancements** - summary-table and demo-matrix-table classes retained for special styling (last-row accent, column alignment) while base table styles come from st-table
3. **Integration tables unchanged** - Small tables inside cards on qa_ecosystem have special styling needs per research

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All demo pages now use consistent table styling via .st-table
- Dark mode works correctly on all tables (VIS-03 complete)
- Ready for Phase 25 landing page work

---
*Phase: 24-visual-consistency*
*Completed: 2026-02-03*
