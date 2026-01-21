---
phase: 02-test-integration
plan: 01
subsystem: testing
tags: [pytest, markers, django-management-command, json-output, traceability]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Requirement model for validation against known requirement IDs
provides:
  - pytest @requirement marker registration
  - extract_links management command for test-requirement link extraction
  - JSON schema for test-requirement links
  - example tests demonstrating all linking patterns
affects: [03-trace-viewer, 04-ci-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pytest custom marker via pytest_configure hook
    - pytest plugin for collection hooks
    - Django management command with JSON output

key-files:
  created:
    - spectrace/conftest.py
    - spectrace/requirements/management/commands/extract_links.py
    - spectrace/tests/__init__.py
    - spectrace/tests/test_example.py
  modified:
    - pyproject.toml

key-decisions:
  - "Marker in both conftest.py and pyproject.toml for programmatic and IDE support"
  - "RequirementCollector as pytest plugin using pytest_collection_modifyitems hook"
  - "Disable pytest-django plugin during collection to avoid DB blocking"
  - "Unknown requirement IDs produce warnings not failures"

patterns-established:
  - "pytest marker pattern: @pytest.mark.requirement(*req_ids, reason=None)"
  - "JSON link schema: version, links array, summary counts"
  - "Management command pattern for pytest integration"

# Metrics
duration: 5min
completed: 2026-01-21
---

# Phase 02 Plan 01: Test-Requirement Linking Summary

**Pytest @requirement marker with extract_links command outputting JSON test-requirement mappings**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-21T05:59:00Z
- **Completed:** 2026-01-21T06:04:34Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Registered @pytest.mark.requirement marker via pytest_configure hook
- Created extract_links Django management command with JSON output
- Implemented RequirementCollector pytest plugin for link extraction
- Example tests demonstrating single/multiple/class-based/parametrized linking
- Unknown requirement ID validation with warnings

## Task Commits

Each task was committed atomically:

1. **Task 1: Register pytest marker and create conftest.py** - `db2a312` (feat)
2. **Task 2: Create extract_links management command** - `88e2970` (feat)
3. **Task 3: Create example tests and verify full extraction** - `d7d7292` (feat)

## Files Created/Modified

- `spectrace/conftest.py` - pytest_configure hook for marker registration
- `spectrace/requirements/management/commands/extract_links.py` - Django command with RequirementCollector plugin
- `spectrace/tests/__init__.py` - Tests package marker
- `spectrace/tests/test_example.py` - Example tests demonstrating all LINK requirements
- `pyproject.toml` - Added marker definition for IDE support

## Decisions Made

- **Dual marker registration:** Both conftest.py (programmatic) and pyproject.toml (IDE/tooling) to ensure marker works in all contexts
- **Disable pytest-django during collection:** Avoids RuntimeError from DB access blocking; collection doesn't need DB
- **io.StringIO for output suppression:** Cleaner than /dev/null, avoids file handle issues

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed -v flag conflict with Django verbosity**
- **Found during:** Task 2 (extract_links command implementation)
- **Issue:** Django BaseCommand already uses -v for verbosity, causing ArgumentError
- **Fix:** Changed to --verbose only (no -v shorthand)
- **Files modified:** spectrace/requirements/management/commands/extract_links.py
- **Verification:** `python manage.py extract_links --help` succeeds
- **Committed in:** 88e2970 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed pytest output suppression breaking plugin**
- **Found during:** Task 3 (testing extract_links)
- **Issue:** Opening /dev/null and assigning to both stdout/stderr broke plugin execution
- **Fix:** Used io.StringIO for clean output suppression
- **Files modified:** spectrace/requirements/management/commands/extract_links.py
- **Verification:** Plugin collects all markers correctly
- **Committed in:** d7d7292 (Task 3 commit)

**3. [Rule 1 - Bug] Fixed -q flag causing argument parsing errors**
- **Found during:** Task 3 (testing extract_links)
- **Issue:** -q flag caused "unrecognized arguments" error in certain contexts
- **Fix:** Removed -q flag, rely on no:terminal plugin for output suppression
- **Files modified:** spectrace/requirements/management/commands/extract_links.py
- **Verification:** Collection works correctly without -q
- **Committed in:** d7d7292 (Task 3 commit)

**4. [Rule 3 - Blocking] Disabled pytest-django plugin during collection**
- **Found during:** Task 3 (testing extract_links)
- **Issue:** pytest-django blocks DB access, causing RuntimeError when validating requirement IDs
- **Fix:** Added `-p no:django` to pytest args for collection-only mode
- **Files modified:** spectrace/requirements/management/commands/extract_links.py
- **Verification:** extract_links runs without DB blocking errors
- **Committed in:** d7d7292 (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (3 bugs, 1 blocking)
**Impact on plan:** All fixes necessary for correct operation. No scope creep.

## Issues Encountered

- Plan expected 7 links but correct count is 8 (minor math error in plan - 1+2+1+1+3=8)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- pytest marker fully functional and registered
- extract_links command outputs valid JSON with complete link metadata
- Foundation ready for Phase 3 (trace viewer) to consume JSON output
- No blockers

---
*Phase: 02-test-integration*
*Completed: 2026-01-21*
