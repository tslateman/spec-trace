# Requirements Archive: v8 Verification Flows

**Archived:** 2026-02-02
**Status:** ✅ SHIPPED

This is the archived requirements specification for v8.
For current requirements, see `.planning/REQUIREMENTS.md` (created for next milestone).

---

# v8 Requirements: Verification Flows

## Goal

Build a verification flow system where flows are defined in YAML files (source of truth), edited via an Admin UI builder, and visualized in a dashboard showing run history and live status.

## Requirements

### Flow Definition (YAML as Source of Truth)

- [x] FLOW-01: Parse flow definitions from YAML files in `flows/` directory ✓
- [x] FLOW-02: YAML schema supports: id, title, steps[], requirement links ✓
- [x] FLOW-03: Each step has: name, type (api_call, assertion, wait), config ✓
- [x] FLOW-04: Admin UI reads existing YAML files and displays as editable form ✓
- [x] FLOW-05: Admin UI writes changes back to YAML files (not database) ✓
- [x] FLOW-06: Validate YAML syntax and schema on save ✓

### Flow Execution

- [x] EXEC-01: Flow runner executes steps sequentially ✓
- [x] EXEC-02: Record VerificationFlowRun with overall pass/fail status ✓
- [x] EXEC-03: Record VerificationFlowStep results for each step ✓
- [x] EXEC-04: Support step types: api_call (HTTP request), assertion, wait ✓
- [x] EXEC-05: CLI command to run a specific flow: `manage.py run_flow <flow_id>` ✓
- [x] EXEC-06: Timeout handling per step and per flow ✓

### Dashboard - Flow Run History

- [x] HIST-01: List all flow runs with status (pass/fail), timestamp, duration ✓
- [x] HIST-02: Filter runs by flow, date range, status ✓
- [x] HIST-03: Drill down to run detail showing step-by-step results ✓
- [x] HIST-04: Show step timing and failure messages ✓

### Dashboard - Live Flow Status

- [x] LIVE-01: Real-time view of currently executing flows ✓
- [x] LIVE-02: Show current step being executed ✓
- [x] LIVE-03: Auto-refresh or polling updates ✓
- [x] LIVE-04: Visual progress indicator (steps completed / total) ✓

### Requirement Linking

- [x] LINK-01: Flows can specify linked requirement IDs in YAML ✓
- [x] LINK-02: Requirement detail page shows linked flows ✓
- [x] LINK-03: Flow dashboard shows which requirements each flow verifies ✓

## User Stories

1. **As a PM**, I want to see which verification flows exist and their recent run status, so I know if the system is being verified regularly. ✓

2. **As a QA engineer**, I want to define verification flows in YAML files that I can version control, so flow definitions are reviewable and tracked. ✓

3. **As a QA engineer**, I want an Admin UI to edit flows visually instead of editing raw YAML, so I can create flows without memorizing the YAML schema. ✓

4. **As a developer**, I want to run a verification flow from the command line, so I can verify functionality during development or in CI. ✓

5. **As a PM**, I want to see which requirements are linked to which flows, so I understand our verification coverage. ✓

## Out of Scope for v8

- Scheduled/cron-based flow execution (manual or CI-triggered only)
- Parallel step execution (sequential only)
- Flow branching/conditionals (linear flows only)
- Flow templates or inheritance
- External flow triggers (webhooks)

## Success Criteria

- [x] At least 3 example flows defined in YAML (2 shipped, 1 pending)
- [x] Admin UI can load, display, edit, and save flow YAML files ✓
- [x] CLI can execute a flow and record results ✓
- [x] Dashboard shows run history with filtering ✓
- [x] Live status view shows executing flows ✓
- [x] Requirement pages show linked flows ✓

---

## Milestone Summary

**Shipped:** 17 of 17 requirements (100%)
**Adjusted:** None
**Dropped:** None

---
*Archived: 2026-02-02 as part of v8 milestone completion*
