---
phase: 20-flow-execution-engine
plan: 01
subsystem: flows
tags: [http, assertions, executors, timeout, requests]

# Dependency graph
requires:
  - phase: 19-yaml-flow-parser
    provides: YAML flow parser, FlowDef/FlowStepDef with type field, _metadata in steps JSON
provides:
  - Step executors module (api_call, assertion, wait)
  - STEP_EXECUTORS registry for type-based dispatch
  - execute_step() dispatcher function
  - Engine with step_timeout and flow_timeout parameters
  - Metadata filtering during execution
affects: [20-02, 21-admin-ui, 22-dashboard]

# Tech tracking
tech-stack:
  added: [responses (test)]
  patterns: [executor-registry, context-passing, signal-based-timeout]

key-files:
  created:
    - spectrace/requirements/flows/executors/__init__.py
    - spectrace/requirements/flows/executors/api_call.py
    - spectrace/requirements/flows/executors/assertion.py
    - spectrace/requirements/flows/executors/wait.py
    - spectrace/requirements/tests/test_executors.py
  modified:
    - spectrace/requirements/flows/engine.py

key-decisions:
  - "Signal-based timeout using SIGALRM for POSIX, skip on Windows"
  - "Executor registry pattern: STEP_EXECUTORS dict maps type -> function"
  - "last_response context key for passing data between api_call and assertion steps"
  - "Response body truncation at 1000 chars to prevent DB bloat"

patterns-established:
  - "Executor function signature: (step_def: dict, context: dict) -> tuple[VerificationCheck, dict]"
  - "Config extraction from step_def['config'] dict"
  - "Context key conventions: last_response, base_url, headers"

# Metrics
duration: 4min
completed: 2026-02-02
---

# Phase 20 Plan 01: Step Executors Summary

**Step executors for api_call, assertion, wait with type-based dispatch and timeout handling in SequentialFlowEngine**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-02T15:03:41Z
- **Completed:** 2026-02-02T15:07:41Z
- **Tasks:** 3/3
- **Files modified:** 6

## Accomplishments

- Step executors module with api_call (HTTP), assertion (field validation), and wait (delay) executors
- STEP_EXECUTORS registry enabling execute_step() to dispatch by step type
- Engine extended with per-step (60s) and per-flow (300s) timeout parameters
- Metadata filtering to skip `_metadata` entries during step iteration
- 27 tests covering all executors, dispatcher, and engine integration

## Task Commits

Each task was committed atomically:

1. **Task 1: Create step executors module** - `404f0bb` (feat)
2. **Task 2: Extend engine with step dispatcher and timeouts** - `37cb2fb` (feat)
3. **Task 3: Write executor tests** - `fa27012` (test)

## Files Created/Modified

- `spectrace/requirements/flows/executors/__init__.py` - STEP_EXECUTORS registry and execute_step dispatcher
- `spectrace/requirements/flows/executors/api_call.py` - HTTP request executor with status verification
- `spectrace/requirements/flows/executors/assertion.py` - Field validation with equals/contains/exists/not_empty operators
- `spectrace/requirements/flows/executors/wait.py` - Configurable delay executor
- `spectrace/requirements/flows/engine.py` - Extended with step dispatcher, timeout handling, metadata filtering
- `spectrace/requirements/tests/test_executors.py` - 27 tests covering all executors

## Decisions Made

1. **Signal-based timeout** - Use `signal.SIGALRM` for step timeouts on POSIX. Windows skips timeout enforcement (documented limitation).

2. **Executor registry pattern** - `STEP_EXECUTORS` dict maps step type strings to executor functions, enabling clean dispatch without if/elif chains.

3. **Context passing conventions** - `last_response` holds JSON response from api_call for assertion steps. `base_url` and `headers` in context enable URL prefixing and header merging.

4. **Response truncation** - Truncate response_body at 1000 chars with "... [truncated]" to prevent database bloat from large API responses.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed backward compatibility for handler error messages**
- **Found during:** Task 2 (engine extension verification)
- **Issue:** Changed error message format broke existing test expecting "Handler error" prefix
- **Fix:** Consolidated ImportError and AttributeError handling to match original engine's "Handler error: {type}: {message}" format
- **Files modified:** spectrace/requirements/flows/executors/__init__.py
- **Verification:** All 38 existing flow tests pass
- **Committed in:** 37cb2fb (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Fix necessary for backward compatibility. No scope creep.

## Issues Encountered

- `responses` library not installed - installed via pip for HTTP mocking in tests

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Step executors complete and tested
- Engine supports all step types (handler, api_call, assertion, wait)
- Ready for plan 20-02: run_flow management command and integration tests
- All 65 tests passing (38 flow + 27 executor)

---
*Phase: 20-flow-execution-engine*
*Completed: 2026-02-02*
