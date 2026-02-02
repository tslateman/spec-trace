---
phase: 21-admin-ui-builder
plan: 03
subsystem: ui
tags: [django, yaml, database-sync, admin]

# Dependency graph
requires:
  - phase: 21-02
    provides: Flow editor list/form views and URL routes
  - phase: 19-02
    provides: sync_yaml_flows_to_db function for database sync
provides:
  - Sync to DB endpoint at /admin/flow-editor/<path>/sync/
  - Complete flow editor workflow (list -> edit -> save -> sync)
affects: [22-flow-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - POST-only endpoint with redirect and messages
    - Reuse existing sync_yaml_flows_to_db for single-file sync

key-files:
  created: []
  modified:
    - spectrace/requirements/views.py
    - spectrace/requirements/urls.py
    - spectrace/templates/admin/requirements/flow_editor_form.html

key-decisions:
  - "Sync endpoint parses single file, syncs single flow (not entire directory)"
  - "Redirect back to edit form after sync with success/error message"

patterns-established:
  - "Single-file sync via parser.parse_file + sync_yaml_flows_to_db([flow])"

# Metrics
duration: 3min
completed: 2026-02-02
---

# Phase 21 Plan 03: Flow Sync to DB Endpoint Summary

**Sync to DB button completes flow editor with database persistence for dashboard display**

## Performance

- **Duration:** 3 min
- **Tasks:** 3 (2 auto + 1 checkpoint)
- **Files modified:** 3

## Accomplishments
- Added /admin/flow-editor/<path>/sync/ POST endpoint for database sync
- Sync to DB button in form template triggers sync with visual feedback
- Human-verified complete workflow: list -> edit -> save -> sync
- Messages framework shows success/error feedback after sync

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Sync to DB endpoint** - `4836d16` (feat)
2. **Task 2: Add Sync to DB button to form template** - `8f45fb8` (feat)
3. **Task 3: Human verification checkpoint** - approved (no commit)

## Files Created/Modified
- `spectrace/requirements/views.py` - Added flow_sync_to_db_view function
- `spectrace/requirements/urls.py` - Added /admin/flow-editor/<path>/sync/ route
- `spectrace/templates/admin/requirements/flow_editor_form.html` - Added Sync to DB button with caption

## Decisions Made
- Sync endpoint handles single file only (not batch sync)
- Uses existing sync_yaml_flows_to_db infrastructure from Phase 19
- Redirect to edit form after sync preserves editing context

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 21 complete: Admin UI backend for flow YAML editing done
- Flow editor at /admin/flow-editor/ fully functional
- All 484 tests passing
- Ready for Phase 22 (Flow Dashboard) to display synced flows

---
*Phase: 21-admin-ui-builder*
*Completed: 2026-02-02*
