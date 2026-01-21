# Milestone v1: MVP

**Status:** ✅ SHIPPED 2026-01-21
**Phases:** 1-4
**Total Plans:** 6

## Overview

SpecTrace delivers requirements traceability in four phases: first establishing the data foundation (specs as markdown with unique IDs), then connecting tests via pytest decorators, then computing verification status and displaying core dashboard metrics, and finally adding advanced features like bidirectional navigation and link validation.

## Phases

### Phase 1: Foundation

**Goal:** System can parse markdown specs and store requirements with unique IDs and hierarchy
**Depends on:** Nothing (first phase)
**Requirements:** SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05
**Success Criteria:**
  1. Developer can run a command that parses specs/ directory and populates database with requirements
  2. Each requirement in the database has a unique ID (REQ-XXX format) extracted from markdown
  3. Requirements reflect parent/child hierarchy from nested markdown structure
  4. Requirements can be filtered by category tags
  5. Spec changes are tracked via git (no separate versioning needed)

Plans:
- [x] 01-01-PLAN.md — Django project setup, database schema, requirement model with treebeard hierarchy
- [x] 01-02-PLAN.md — Spec parser (python-frontmatter + markdown) and CLI import command

### Phase 2: Test Integration

**Goal:** Tests can be annotated with requirement IDs and the system extracts these links
**Depends on:** Phase 1
**Requirements:** LINK-01, LINK-02, LINK-03, LINK-04
**Success Criteria:**
  1. Developer can use @pytest.mark.requirement("REQ-XXX") decorator on tests
  2. Multiple tests can link to the same requirement (many-to-one)
  3. One test can link to multiple requirements (one-to-many)
  4. Developer can run a command that extracts all requirement annotations from test files

Plans:
- [x] 02-01-PLAN.md — pytest marker registration, extract_links CLI command, example tests

### Phase 3: Verification & Core Dashboard

**Goal:** System computes verification status and displays requirements with pass/fail/untested indicators
**Depends on:** Phase 2
**Requirements:** VERIFY-01, VERIFY-02, VERIFY-03, DASH-01, DASH-02, DASH-04
**Success Criteria:**
  1. Each requirement shows status: Passing (all linked tests pass), Failing (any linked test fails), or Untested (no linked tests)
  2. System can import pytest results from JUnit XML
  3. Dashboard shows all requirements organized by hierarchy
  4. Dashboard shows summary metrics: total requirements, % passing, % failing, % untested
  5. Untested requirements are visually highlighted (coverage gaps obvious at a glance)

Plans:
- [x] 03-01-PLAN.md — JUnit XML import, TestRun/TestResult models, verification status computation
- [x] 03-02-PLAN.md — Django-unfold dashboard with hierarchical tree view, metrics banner, coverage highlighting

### Phase 4: Dashboard Features & Navigation

**Goal:** Users can explore traceability with search, filters, and bidirectional navigation
**Depends on:** Phase 3
**Requirements:** DASH-03 (deferred), DASH-05, DASH-06, NAV-01, NAV-02, NAV-03 (deferred)
**Success Criteria:**
  1. ~~User can view traceability matrix (requirements vs. tests grid)~~ DEFERRED
  2. User can search requirements by ID, text, status, or tag ✅
  3. User can filter requirements by category/tag ✅
  4. Clicking a requirement shows all linked tests and their status ✅
  5. Clicking a test shows all linked requirements ✅
  6. ~~When a spec file changes, system shows which tests are affected~~ DEFERRED

Extended features (beyond original scope):
- [x] Bidirectional navigation (linked_tests, linked_requirements in admin)
- [x] Link validation command (`validate_links` for CI)
- [x] In-app validation system (models, import command, API)
- [x] SLO integration (OpenSLO parser, import, status tracking)
- [x] REST API endpoints for external systems
- [x] Linear integration for issue sync

---

## Milestone Summary

**Decimal Phases:** None (no urgent insertions needed)

**Key Decisions:**
- Use django-treebeard MP_Node for hierarchical requirements
- Specs in codebase, not Notion — version control, no drift, reviewable changes
- Markdown format — human-readable, easy for PMs to write/review
- pytest annotations — native to existing test workflow
- Denormalized verification_status on Requirement for dashboard performance
- django-unfold for modern Tailwind-based admin UI

**Issues Resolved:**
- Test nodeid format mismatch (JUnit XML vs extract_links) — fixed with _normalize_nodeid()
- Missing demo data — created 9 diverse specs and setup script

**Issues Deferred:**
- DASH-03: Traceability matrix view
- NAV-03: Impact analysis (spec change → affected tests)

**Technical Debt Incurred:**
- UAT not fully completed (9/10 tests pending user verification)
- REQUIREMENTS.md documentation drift (marked pending, actually complete)

---

_For current project status, see .planning/ROADMAP.md (created for next milestone)_
