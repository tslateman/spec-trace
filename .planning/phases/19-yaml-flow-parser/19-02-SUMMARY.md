---
phase: 19-yaml-flow-parser
plan: 02
subsystem: flows
tags: [yaml, parser, django-management-command, sync]

# Dependency graph
requires:
  - phase: 19-01
    provides: YAMLFlowParser, FlowDef with requirements/source_file fields
provides:
  - sync_yaml_flows_to_db function for database syncing
  - parse_flows management command with --dry-run and --clear
  - Comprehensive test coverage for parser and sync
affects: [19-03, 20, 21]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Metadata stored in JSONField as _metadata key (avoids schema changes)
    - BaseImportCommand pattern for management commands

key-files:
  created:
    - spectrace/requirements/management/commands/parse_flows.py
    - spectrace/requirements/tests/test_flow_parser.py
  modified:
    - spectrace/requirements/flows/sync.py

key-decisions:
  - "Store metadata (source_file, requirements) in steps JSON as _metadata key - Phase 23 adds proper M2M linking"
  - "clear_existing deletes only flows matching the names being synced, not all YAML-sourced flows"

patterns-established:
  - "Metadata in JSONField: First element of steps array with _metadata key for storing source_file and requirements"

# Metrics
duration: 3min
completed: 2026-02-02
---

# Phase 19 Plan 02: Management Command and Sync Summary

**parse_flows management command with sync_yaml_flows_to_db for syncing YAML flows to database**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-02T14:31:21Z
- **Completed:** 2026-02-02T14:34:06Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Extended sync.py with sync_yaml_flows_to_db function storing metadata in steps JSON
- Created parse_flows management command following BaseImportCommand pattern
- Added 29 comprehensive tests covering parser validation, sync behavior, and CLI

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend sync.py for YAML flows** - `863ead1` (feat)
2. **Task 2: Create parse_flows management command** - `1f29ec3` (feat)
3. **Task 3: Create comprehensive tests** - `51f06cb` (test)

## Files Created/Modified

- `spectrace/requirements/flows/sync.py` - Added sync_yaml_flows_to_db function for YAML flow syncing
- `spectrace/requirements/management/commands/parse_flows.py` - Django command for parsing and syncing YAML flows
- `spectrace/requirements/tests/test_flow_parser.py` - 29 tests covering parser, sync, and CLI

## Decisions Made

1. **Metadata storage approach:** Store source_file and requirements in steps JSONField as `_metadata` key in first position. This avoids schema changes while preserving traceability data. Phase 23 will add proper M2M requirement linking.

2. **Clear behavior:** `clear_existing=True` deletes only flows matching the names in the provided list, not all YAML-sourced flows. This prevents accidental deletion of unrelated flows.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- sync_yaml_flows_to_db ready for registry integration (19-03)
- parse_flows command works with flows/ directory
- YAML flows appear in database alongside code-defined flows

---
*Phase: 19-yaml-flow-parser*
*Completed: 2026-02-02*
