---
phase: 20-flow-execution-engine
plan: 02
subsystem: cli
tags: [django-management-command, flow-execution, verification]

# Dependency graph
requires:
  - phase: 20-01
    provides: Step executors (api_call, assertion, wait) and SequentialFlowEngine
provides:
  - run_flow management command for CLI-based flow execution
  - Flow lookup by name or ID
  - JSON context passing
  - Configurable timeouts
affects: [21-admin-ui, 22-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Management command with positional flow identifier
    - Exit code 0/1 based on flow status

key-files:
  created:
    - spectrace/requirements/management/commands/run_flow.py
    - spectrace/requirements/tests/test_run_flow_command.py
  modified: []

key-decisions:
  - "Flow lookup tries numeric ID first, then name lookup"
  - "Exit code 1 via sys.exit(1) for failed flows"
  - "Use self.style.SUCCESS/ERROR/WARNING for colored output"

patterns-established:
  - "Flow lookup pattern: try int(), then name, then CommandError"
  - "CLI output format: Flow name, status, duration, step-by-step results"

# Metrics
duration: 2min
completed: 2026-02-02
---

# Phase 20 Plan 02: run_flow Management Command Summary

**CLI command to execute verification flows by name or ID with JSON context and configurable timeouts**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-02T15:09:46Z
- **Completed:** 2026-02-02T15:12:11Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- run_flow command accepts flow by name or numeric ID
- JSON context passing via --context flag
- Configurable step and flow timeouts
- Colored output with [PASS]/[FAIL] status markers
- Exit code 0 for passed, 1 for failed flows
- 15 tests covering lookup, execution, context, timeout, and integration scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: Create run_flow management command** - `6d1bbaa` (feat)
2. **Task 2: Write command tests** - `bfc63be` (test)
3. **Task 3: Integration test with example flow** - `831f86f` (test)

## Files Created/Modified
- `spectrace/requirements/management/commands/run_flow.py` - CLI command (154 lines)
- `spectrace/requirements/tests/test_run_flow_command.py` - Tests (401 lines)

## Decisions Made
- **Flow lookup order:** Try `int(flow_id)` first for numeric lookup, then name lookup, then CommandError
- **Exit strategy:** Use `sys.exit(1)` for failed flows rather than raising exception
- **Output styling:** Use Django's self.style helpers for colored terminal output

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- run_flow command ready for use in CI/CD pipelines
- Flow execution infrastructure complete (Phase 20 done)
- Ready for Phase 21: Admin UI for flow management

---
*Phase: 20-flow-execution-engine*
*Completed: 2026-02-02*
