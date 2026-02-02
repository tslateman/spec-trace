---
phase: 21-admin-ui-builder
plan: 01
subsystem: api
tags: [ruamel-yaml, yaml, flow-editor, file-io, security]

# Dependency graph
requires:
  - phase: 19-flow-yaml-parser
    provides: YAMLFlowParser, FlowParseError, FlowDef
provides:
  - Flow editor service with list, load, save functions
  - Path traversal security validation
  - Comment-preserving YAML round-trip editing
affects: [21-02-flow-list-api, 21-03-flow-edit-api, admin-ui-flows]

# Tech tracking
tech-stack:
  added: [ruamel-yaml]
  patterns: [validate-before-write, path-traversal-protection]

key-files:
  created:
    - spectrace/requirements/flow_editor.py
    - spectrace/requirements/tests/test_flow_editor.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Extension check before path traversal check in validate_flow_path"
  - "Return dict from load_flow_for_editing (not FlowDef) for form editing flexibility"
  - "Validate content via YAMLFlowParser before save to ensure YAML correctness"

patterns-established:
  - "Path traversal protection: resolve path then check relative_to(FLOWS_DIR)"
  - "Comment preservation: load existing file with ruamel.yaml, update fields, write back"

# Metrics
duration: 8min
completed: 2026-02-02
---

# Phase 21 Plan 01: Flow Editor Service Summary

**Flow editor service layer with path-secure YAML read/write using ruamel.yaml for comment preservation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-02T15:44:37Z
- **Completed:** 2026-02-02T15:52:30Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added ruamel.yaml dependency for comment-preserving YAML editing
- Created flow_editor.py with validate_flow_path, get_flow_files, load_flow_for_editing, save_flow
- Path traversal attacks blocked via resolve() + relative_to() check
- 17 unit tests covering validation, security, loading, saving, and comment preservation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ruamel.yaml dependency** - `417a0ff` (chore)
2. **Task 2: Create flow editor service module** - `71a2c39` (feat)
3. **Task 3: Add unit tests for flow editor service** - `aa0900b` (test)

## Files Created/Modified
- `pyproject.toml` - Added ruamel-yaml>=0.19.1 dependency
- `uv.lock` - Updated lock file with ruamel-yaml
- `spectrace/requirements/flow_editor.py` - Flow editor service (169 lines)
- `spectrace/requirements/tests/test_flow_editor.py` - Unit tests (222 lines, 17 tests)

## Decisions Made
- Extension check (.yaml/.yml) runs before path traversal check in validate_flow_path
- load_flow_for_editing returns raw dict (not FlowDef) to preserve flexibility for form editing
- save_flow validates via YAMLFlowParser._validate_and_build_flow before writing
- When file exists, load existing content to preserve comments, then update fields

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Flow editor service ready for API endpoints (Plan 21-02, 21-03)
- FLOWS_DIR constant and validate_flow_path available for import
- get_flow_files returns metadata for list endpoint
- load_flow_for_editing and save_flow ready for detail/edit endpoints

---
*Phase: 21-admin-ui-builder*
*Completed: 2026-02-02*
