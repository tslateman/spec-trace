# Milestone v8: Verification Flows

**Status:** In Progress
**Phases:** 19-23
**Goal:** YAML-based verification flows with Admin UI builder and dashboard views

## Overview

Build a verification flow system where:
1. Flows are defined in YAML files (source of truth)
2. Admin UI reads/writes YAML files for editing
3. Dashboard shows flow run history and live status
4. Flows link to requirements for traceability

Existing infrastructure: VerificationFlow, VerificationFlowRun, VerificationFlowStep models already exist in the codebase.

## Phases

### Phase 19: YAML Flow Parser ✓

**Status:** Complete (2026-02-02)
**Goal:** Parse flow definitions from YAML files.

**Requirements:**
- FLOW-01: Parse flow definitions from YAML files in `flows/` directory ✓
- FLOW-02: YAML schema supports: id, title, steps[], requirement links ✓
- FLOW-03: Each step has: name, type (api_call, assertion, wait), config ✓

**Deliverables:**
- `flows/` directory convention ✓
- YAML schema definition and validation ✓
- Parser service: `flows/parser.py` (234 lines) ✓
- Management command: `parse_flows` ✓
- Example flow YAML files (2 flows) ✓

**Plans:** 2 plans (complete)
- [x] 19-01-PLAN.md - YAML parser and extended dataclasses
- [x] 19-02-PLAN.md - Management command and sync infrastructure

**Commits:** 9 total

---

### Phase 20: Flow Execution Engine ✓

**Status:** Complete (2026-02-02)
**Goal:** Execute flows and record results.

**Requirements:**
- EXEC-01: Flow runner executes steps sequentially ✓
- EXEC-02: Record VerificationFlowRun with overall pass/fail status ✓
- EXEC-03: Record VerificationFlowStep results for each step ✓
- EXEC-04: Support step types: api_call (HTTP request), assertion, wait ✓
- EXEC-05: CLI command to run a specific flow: `manage.py run_flow <flow_id>` ✓
- EXEC-06: Timeout handling per step and per flow ✓

**Deliverables:**
- Step executors module: `flows/executors/` (api_call.py, assertion.py, wait.py) ✓
- Extended SequentialFlowEngine with step type dispatcher and timeouts ✓
- Management command: `run_flow` (154 lines) ✓
- Tests for execution engine: 42 tests ✓

**Plans:** 2 plans (complete)
- [x] 20-01-PLAN.md - Step executors + engine extension (Wave 1)
- [x] 20-02-PLAN.md - run_flow command + integration tests (Wave 2)

**Commits:** 8 total

---

### Phase 21: Admin UI Builder ✓

**Status:** Complete (2026-02-02)
**Goal:** Visual editor for YAML flow files.

**Requirements:**
- FLOW-04: Admin UI reads existing YAML files and displays as editable form ✓
- FLOW-05: Admin UI writes changes back to YAML files (not database) ✓
- FLOW-06: Validate YAML syntax and schema on save ✓

**Deliverables:**
- Flow editor service: `flow_editor.py` (170 lines, ruamel.yaml for round-trip) ✓
- Flow list view: `/admin/flow-editor/` ✓
- Flow edit form with Alpine.js step management ✓
- Save action writes to YAML file ✓
- Sync to DB button for database update ✓
- Validation errors shown in UI ✓

**Plans:** 3 plans (complete)
- [x] 21-01-PLAN.md — Backend service layer (ruamel.yaml, path validation, CRUD)
- [x] 21-02-PLAN.md — Admin views and templates (list + edit form)
- [x] 21-03-PLAN.md — Sync to DB button + human verification

**Tests:** 17 unit tests
**Commits:** 10 total

---

### Phase 22: Dashboard - History & Live Status

**Goal:** Dashboard views for flow monitoring.

**Requirements:**
- HIST-01: List all flow runs with status, timestamp, duration
- HIST-02: Filter runs by flow, date range, status
- HIST-03: Drill down to run detail showing step-by-step results
- HIST-04: Show step timing and failure messages
- LIVE-01: Real-time view of currently executing flows
- LIVE-02: Show current step being executed
- LIVE-03: Auto-refresh or polling updates
- LIVE-04: Visual progress indicator

**Deliverables:**
- Flow runs list view: `admin/flow_runs.html`
- Flow run detail view: `admin/flow_run_detail.html`
- Live status view: `admin/flow_live.html`
- Filtering by flow, date, status

---

### Phase 23: Requirement Linking

**Goal:** Connect flows to requirements for traceability.

**Requirements:**
- LINK-01: Flows can specify linked requirement IDs in YAML
- LINK-02: Requirement detail page shows linked flows
- LINK-03: Flow dashboard shows which requirements each flow verifies

**Deliverables:**
- M2M field on VerificationFlow model
- Migration for the M2M table
- Update sync_yaml_flows_to_db to populate M2M (remove _metadata workaround)
- VerificationFlowAdmin registration with requirements display
- RequirementAdmin linked_flows display method
- Flow list/detail views show linked requirements

**Plans:** 2 plans
- [ ] 23-01-PLAN.md — Model M2M field, migration, sync logic update
- [ ] 23-02-PLAN.md — Admin UI updates (VerificationFlowAdmin, RequirementAdmin)

---

## Requirements Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FLOW-01 | Phase 19 | Complete |
| FLOW-02 | Phase 19 | Complete |
| FLOW-03 | Phase 19 | Complete |
| EXEC-01 | Phase 20 | Complete |
| EXEC-02 | Phase 20 | Complete |
| EXEC-03 | Phase 20 | Complete |
| EXEC-04 | Phase 20 | Complete |
| EXEC-05 | Phase 20 | Complete |
| EXEC-06 | Phase 20 | Complete |
| FLOW-04 | Phase 21 | Complete |
| FLOW-05 | Phase 21 | Complete |
| FLOW-06 | Phase 21 | Complete |
| HIST-01 | Phase 22 | Pending |
| HIST-02 | Phase 22 | Pending |
| HIST-03 | Phase 22 | Pending |
| HIST-04 | Phase 22 | Pending |
| LIVE-01 | Phase 22 | Pending |
| LIVE-02 | Phase 22 | Pending |
| LIVE-03 | Phase 22 | Pending |
| LIVE-04 | Phase 22 | Pending |
| LINK-01 | Phase 23 | Pending |
| LINK-02 | Phase 23 | Pending |
| LINK-03 | Phase 23 | Pending |

## Success Criteria

- [ ] At least 3 example flows defined in YAML
- [x] Admin UI can load, display, edit, and save flow YAML files
- [x] CLI can execute a flow and record results
- [ ] Dashboard shows run history with filtering
- [ ] Live status view shows executing flows
- [ ] Requirement pages show linked flows

## Out of Scope

- Scheduled/cron-based flow execution (manual or CI-triggered only)
- Parallel step execution (sequential only)
- Flow branching/conditionals (linear flows only)
- Flow templates or inheritance
- External flow triggers (webhooks)
