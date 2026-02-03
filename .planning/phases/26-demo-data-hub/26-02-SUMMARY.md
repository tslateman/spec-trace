---
phase: 26-demo-data-hub
plan: 02
subsystem: demo
tags: [pytest, demo-data, vendor-coverage, verification-status]

# Dependency graph
requires:
  - phase: 26-01
    provides: Sample spec files with 3-level hierarchy
provides:
  - Sample tests with mixed verification outcomes (passing/failing/untested)
  - Vendor demo setup command and documentation
  - Realistic dashboard demo data
affects: [26-03, 26-04, guided-tour, onboarding]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest.mark.requirement decorator for test-requirement linking"
    - "extract_links -> import_results workflow for test linkage"

key-files:
  created:
    - tests/sample/test_sample_requirements.py
    - specs/demo/DEMO-SCENARIOS.md
    - spectrace/requirements/management/commands/setup_vendor_demo.py
  modified: []

key-decisions:
  - "Used extract_links command to generate requirement links from pytest markers"
  - "Created management command for vendor demo setup (was missing from codebase)"

patterns-established:
  - "Demo data setup: parse specs, run tests, extract links, import results with links"

# Metrics
duration: 3min
completed: 2026-02-03
---

# Phase 26 Plan 02: Demo Data Linkage Summary

**Sample tests linked to requirements showing mixed verification status (2 passing, 1 failing, 4 untested); vendor demo produces realistic scenarios with 4 vendors and regression pattern**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-03T16:34:59Z
- **Completed:** 2026-02-03T16:38:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Sample tests linked to requirements with mixed verification status
- Vendor demo setup command created and verified
- Demo scenarios documented for reference

## Task Commits

Each task was committed atomically:

1. **Task 1: Create sample tests with mixed verification outcomes** - `496c0e1` (test)
2. **Task 2: Verify and document vendor demo scenarios** - `41355e7` (docs)

## Files Created/Modified
- `tests/sample/test_sample_requirements.py` - 4 tests with @pytest.mark.requirement decorators linking to sample specs
- `specs/demo/DEMO-SCENARIOS.md` - Documentation of vendor demo scenarios and setup instructions
- `spectrace/requirements/management/commands/setup_vendor_demo.py` - Management command wrapping setup_vendor_demo service function

## Decisions Made

**1. Test linkage workflow**
Used the extract_links command to generate requirement links from pytest markers, then import_results with --links flag. This creates TestResult records linked to Requirement records via ManyToMany relationship.

**2. Created missing management command**
The setup_vendor_demo function existed in services/vendor_demo.py but had no management command wrapper. Created one following the pattern of setup_flow_demo.py.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing management command for vendor demo**
- **Found during:** Task 2 (Verify vendor demo)
- **Issue:** `python manage.py setup_vendor_demo` failed - command didn't exist
- **Fix:** Created management command at spectrace/requirements/management/commands/setup_vendor_demo.py
- **Files modified:** spectrace/requirements/management/commands/setup_vendor_demo.py
- **Verification:** Command runs successfully, creates 4 vendors with 16 validations
- **Committed in:** 41355e7 (Task 2 commit)

**2. [Rule 1 - Bug] Database migrations needed**
- **Found during:** Task 1 (Import test results)
- **Issue:** `import_results` command failed with "no such table: requirements_testrun"
- **Fix:** Ran `python manage.py migrate` to create database tables
- **Files modified:** Database schema (not tracked in git)
- **Verification:** Import command succeeded after migrations
- **Committed in:** N/A (database state, not code)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for task completion. No scope creep.

## Issues Encountered

**Test linkage workflow discovery**
Initially attempted to import test results without the --links flag. The system requires a two-step process:
1. Extract links from pytest markers using `extract_links` command
2. Import results with `--links` flag to connect TestResult to Requirement records

This is documented in the codebase but required exploration to discover the correct workflow.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Demo data is ready for dashboard verification:
- Sample requirements show mixed verification status (2 passing, 1 failing, 4 untested)
- Vendor demo provides 4 vendors with varied pass rates (80%, 75%, 100%, 50%)
- Regression scenario demonstrates status change detection (OpenKey pass -> fail)
- 3-level hierarchy demonstrates requirement depth visualization

Ready for DEMO-03 (dashboard verification) and DEMO-04 (vendor page verification).

---
*Phase: 26-demo-data-hub*
*Completed: 2026-02-03*
