---
phase: 23-requirement-linking
plan: 01
subsystem: database
tags: [django, m2m, verification-flows, requirements, migration]

# Dependency graph
requires:
  - phase: 19-yaml-flow-parser
    provides: VerificationFlow model and sync_yaml_flows_to_db
provides:
  - M2M relationship between VerificationFlow and Requirement
  - Automatic requirement linking during YAML flow sync
  - Bidirectional access (flow.requirements, req.verification_flows)
affects: [23-02, dashboard-views, requirement-traceability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "M2M linking via external_id lookup (not FK)"
    - "_sync_flow_requirements helper for atomic M2M updates"

key-files:
  created:
    - spectrace/requirements/migrations/0011_verificationflow_requirements.py
  modified:
    - spectrace/requirements/models.py
    - spectrace/requirements/flows/sync.py
    - spectrace/requirements/tests/test_flow_parser.py

key-decisions:
  - "Link requirements by external_id lookup, not FK (requirements may not exist yet)"
  - "Log warnings for missing requirements instead of failing sync"
  - "Remove requirements from _metadata (now via M2M, source_file remains)"

patterns-established:
  - "M2M linking pattern: Look up by external_id, warn on missing, use .set() for atomic replacement"

# Metrics
duration: 15min
completed: 2026-02-02
---

# Phase 23 Plan 01: Requirement M2M Linking Summary

**VerificationFlow.requirements M2M field with sync linking via external_id lookup and warning-only on missing**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-02T16:30:00Z
- **Completed:** 2026-02-02T16:45:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added requirements M2M field to VerificationFlow model
- Created and applied migration 0011 for join table
- Updated sync_yaml_flows_to_db to link requirements via M2M
- Added 3 new tests for M2M linking behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Add requirements M2M field** - `d85ace5` (feat)
2. **Task 2: Create and apply migration** - `e17d8b0` (chore)
3. **Task 3: Update sync to use M2M** - `f82ea77` (feat)

## Files Created/Modified
- `spectrace/requirements/models.py` - Added requirements ManyToManyField to VerificationFlow
- `spectrace/requirements/migrations/0011_verificationflow_requirements.py` - Migration for M2M join table
- `spectrace/requirements/flows/sync.py` - Added _sync_flow_requirements helper, updated sync logic
- `spectrace/requirements/tests/test_flow_parser.py` - Added 3 tests, updated metadata test

## Decisions Made
- Used external_id lookup instead of FK to handle requirements that may not exist in database
- Missing requirements are logged as warnings (not errors) to prevent sync failures
- Removed requirements from _metadata dict since they're now properly stored via M2M

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test for metadata structure change**
- **Found during:** Task 3 (sync update)
- **Issue:** Existing test expected requirements in _metadata, but we removed it
- **Fix:** Updated test to assert requirements NOT in metadata
- **Files modified:** spectrace/requirements/tests/test_flow_parser.py
- **Verification:** All 33 tests pass
- **Committed in:** f82ea77 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Test update was necessary for correctness. No scope creep.

## Issues Encountered
- Requirement model uses django-treebeard MP_Node, requires add_root() instead of create() - fixed in new tests

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- M2M foundation complete for requirement linking
- Ready for Plan 23-02: API/view updates to expose M2M links
- Can query flow.requirements.all() and req.verification_flows.all() bidirectionally

---
*Phase: 23-requirement-linking*
*Completed: 2026-02-02*
