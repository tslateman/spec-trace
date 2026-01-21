# Roadmap: SpecTrace

## Overview

SpecTrace delivers requirements traceability in four phases: first establishing the data foundation (specs as markdown with unique IDs), then connecting tests via pytest decorators, then computing verification status and displaying core dashboard metrics, and finally adding advanced features like the traceability matrix and bidirectional navigation. Each phase delivers a complete, verifiable capability that builds toward the core value: PMs can see which requirements are verified by passing tests.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (e.g., 2.1): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation** - Data model and spec parsing from markdown files
- [x] **Phase 2: Test Integration** - pytest plugin for linking tests to requirements
- [ ] **Phase 3: Verification & Core Dashboard** - Status computation and essential views
- [ ] **Phase 4: Dashboard Features & Navigation** - Traceability matrix, search, and bidirectional navigation

## Phase Details

### Phase 1: Foundation
**Goal**: System can parse markdown specs and store requirements with unique IDs and hierarchy
**Depends on**: Nothing (first phase)
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05
**Success Criteria** (what must be TRUE):
  1. Developer can run a command that parses specs/ directory and populates database with requirements
  2. Each requirement in the database has a unique ID (REQ-XXX format) extracted from markdown
  3. Requirements reflect parent/child hierarchy from nested markdown structure
  4. Requirements can be filtered by category tags
  5. Spec changes are tracked via git (no separate versioning needed)
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Django project setup, database schema, requirement model with treebeard hierarchy
- [x] 01-02-PLAN.md — Spec parser (python-frontmatter + markdown) and CLI import command

### Phase 2: Test Integration
**Goal**: Tests can be annotated with requirement IDs and the system extracts these links
**Depends on**: Phase 1
**Requirements**: LINK-01, LINK-02, LINK-03, LINK-04
**Success Criteria** (what must be TRUE):
  1. Developer can use @pytest.mark.requirement("REQ-XXX") decorator on tests
  2. Multiple tests can link to the same requirement (many-to-one)
  3. One test can link to multiple requirements (one-to-many)
  4. Developer can run a command that extracts all requirement annotations from test files
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md — pytest marker registration, extract_links CLI command, example tests

### Phase 3: Verification & Core Dashboard
**Goal**: System computes verification status and displays requirements with pass/fail/untested indicators
**Depends on**: Phase 2
**Requirements**: VERIFY-01, VERIFY-02, VERIFY-03, DASH-01, DASH-02, DASH-04
**Success Criteria** (what must be TRUE):
  1. Each requirement shows status: Passing (all linked tests pass), Failing (any linked test fails), or Untested (no linked tests)
  2. System can import pytest results from JUnit XML
  3. Dashboard shows all requirements organized by hierarchy
  4. Dashboard shows summary metrics: total requirements, % passing, % failing, % untested
  5. Untested requirements are visually highlighted (coverage gaps obvious at a glance)
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md — JUnit XML import, TestRun/TestResult models, verification status computation
- [ ] 03-02-PLAN.md — Django-unfold dashboard with hierarchical tree view, metrics banner, coverage highlighting

### Phase 4: Dashboard Features & Navigation
**Goal**: Users can explore traceability with matrix view, search, and bidirectional navigation
**Depends on**: Phase 3
**Requirements**: DASH-03, DASH-05, DASH-06, NAV-01, NAV-02, NAV-03
**Success Criteria** (what must be TRUE):
  1. User can view traceability matrix (requirements vs. tests grid)
  2. User can search requirements by ID, text, status, or tag
  3. User can filter requirements by category/tag
  4. Clicking a requirement shows all linked tests and their status
  5. Clicking a test shows all linked requirements
  6. When a spec file changes, system shows which tests are affected (impact analysis)
**Plans**: TBD

Plans:
- [ ] 04-01: Traceability matrix view and search/filter functionality
- [ ] 04-02: Bidirectional navigation and impact analysis

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete | 2026-01-19 |
| 2. Test Integration | 1/1 | Complete | 2026-01-20 |
| 3. Verification & Core Dashboard | 0/2 | Planned | - |
| 4. Dashboard Features & Navigation | 0/2 | Not started | - |

---
*Roadmap created: 2026-01-19*
*Phase 1 planned: 2026-01-19*
*Depth: quick (4 phases, 7 plans total)*
*Phase 1 completed: 2026-01-19*
*Phase 2 planned: 2026-01-20*
*Phase 2 completed: 2026-01-20*
*Phase 3 planned: 2026-01-20*
