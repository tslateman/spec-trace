# Requirements Archive: v1 MVP

**Archived:** 2026-01-21
**Status:** ✅ SHIPPED

This is the archived requirements specification for v1.
For current requirements, see `.planning/REQUIREMENTS.md` (created for next milestone).

---

# Requirements: SpecTrace

**Defined:** 2026-01-19
**Core Value:** PMs can see, at any moment, which requirements are verified by passing tests

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Spec Management

- [x] **SPEC-01**: System parses markdown files from specs/ directory to extract requirements
- [x] **SPEC-02**: Each requirement has a unique ID (REQ-XXX format) defined in markdown
- [x] **SPEC-03**: Requirements support parent/child hierarchy via nested markdown structure
- [x] **SPEC-04**: Requirements can be tagged with categories (feature area, priority)
- [x] **SPEC-05**: Spec changes are tracked via git history (no separate versioning system)

### Test Linking

- [x] **LINK-01**: Tests can be annotated with requirement IDs via pytest decorator
- [x] **LINK-02**: Multiple tests can link to the same requirement
- [x] **LINK-03**: One test can link to multiple requirements
- [x] **LINK-04**: System extracts requirement annotations from test files

### Verification

- [x] **VERIFY-01**: Each requirement shows verification status (Passing/Failing/Untested)
- [x] **VERIFY-02**: Status is derived from linked test results (all pass = Passing, any fail = Failing, no tests = Untested)
- [x] **VERIFY-03**: Test results can be imported from pytest output (JUnit XML or similar)

### Dashboard

- [x] **DASH-01**: Dashboard shows all requirements organized by hierarchy
- [x] **DASH-02**: Dashboard shows summary metrics (total requirements, % passing, % failing, % untested)
- [ ] **DASH-03**: Traceability matrix view shows requirements vs. tests grid — DEFERRED to v2
- [x] **DASH-04**: Untested requirements are visually highlighted (coverage gaps)
- [x] **DASH-05**: User can search requirements by ID, text, status, or tag
- [x] **DASH-06**: User can filter requirements by category/tag

### Navigation

- [x] **NAV-01**: Clicking a requirement shows all linked tests and their status
- [x] **NAV-02**: Clicking a test shows all linked requirements
- [ ] **NAV-03**: When a spec file changes, system shows which tests are affected (impact analysis) — DEFERRED to v2

## Extended Features (Added During v1)

Beyond original requirements, shipped:

- [x] **VALIDATE-01**: Link validation command for CI/CD drift detection
- [x] **INAPP-01**: In-app validation support (requirements verified via product UI)
- [x] **SLO-01**: SLO integration with OpenSLO YAML support
- [x] **API-01**: REST API endpoints for external system integration
- [x] **LINEAR-01**: Linear integration for syncing issues as requirements

## v2 Requirements (Deferred)

Tracked but not shipped in v1.

### CI Integration

- **CI-01**: Webhooks receive test results from CI pipeline
- **CI-02**: Dashboard updates in real-time as CI runs complete
- **CI-03**: Test execution history tracked over time

### Advanced Analytics

- **ANLYT-01**: Historical coverage trends (coverage % over time chart)
- **ANLYT-02**: Multi-stakeholder views (PM/Engineer/QA see role-appropriate data)
- **ANLYT-03**: Coverage metrics dashboard (detailed breakdown by category)

### Data Operations

- **DATA-01**: Bulk import requirements from CSV
- **DATA-02**: Export traceability report to CSV/Markdown

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Built-in test execution | Reinvents pytest/CI; consume results, don't run tests |
| Electronic signatures | Regulated industry feature; not targeting compliance |
| Complex approval workflows | Enterprise overhead; delays adoption |
| Real-time collaborative editing | Git handles this; specs edited in IDE |
| Custom requirement attributes | Configuration complexity; fixed schema for v1 |
| Multiple requirement types | Requirements only; integrate with Linear for issues |
| AI requirement generation | Gimmick; requirements need human judgment |
| ReqIF import/export | Enterprise standard; CSV/Markdown sufficient |
| Variant/configuration management | Automotive/aerospace complexity; single variant |
| Multi-repo aggregation | Single repo for v1; defer complexity |
| Notion/Linear sync | Specs live in codebase, not external tools |

## Traceability

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SPEC-01 | Phase 1 | ✅ Complete |
| SPEC-02 | Phase 1 | ✅ Complete |
| SPEC-03 | Phase 1 | ✅ Complete |
| SPEC-04 | Phase 1 | ✅ Complete |
| SPEC-05 | Phase 1 | ✅ Complete |
| LINK-01 | Phase 2 | ✅ Complete |
| LINK-02 | Phase 2 | ✅ Complete |
| LINK-03 | Phase 2 | ✅ Complete |
| LINK-04 | Phase 2 | ✅ Complete |
| VERIFY-01 | Phase 3 | ✅ Complete |
| VERIFY-02 | Phase 3 | ✅ Complete |
| VERIFY-03 | Phase 3 | ✅ Complete |
| DASH-01 | Phase 3 | ✅ Complete |
| DASH-02 | Phase 3 | ✅ Complete |
| DASH-03 | Phase 4 | ⏳ Deferred |
| DASH-04 | Phase 3 | ✅ Complete |
| DASH-05 | Phase 4 | ✅ Complete |
| DASH-06 | Phase 4 | ✅ Complete |
| NAV-01 | Phase 4 | ✅ Complete |
| NAV-02 | Phase 4 | ✅ Complete |
| NAV-03 | Phase 4 | ⏳ Deferred |

**Coverage:**
- v1 requirements: 21 total
- Shipped: 19 (90%)
- Deferred: 2 (10%)

---

## Milestone Summary

**Shipped:** 19 of 21 v1 requirements (90%)

**Adjusted:** None — all requirements shipped as originally specified

**Dropped:** None

**Deferred:**
- DASH-03 (Traceability matrix) — complexity vs. value; bidirectional navigation sufficient for v1
- NAV-03 (Impact analysis) — requires git integration complexity; defer to v2

---
*Archived: 2026-01-21 as part of v1 milestone completion*
