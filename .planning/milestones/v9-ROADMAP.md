# Milestone v9: Demo & Marketing Polish

**Status:** SHIPPED 2026-02-03
**Phases:** 24-28
**Total Plans:** 7

## Overview

Make SpecTrace's value immediately clear to engineering leads evaluating the tool. Starting with visual consistency as the foundation (Phase 24), then building the landing page (Phase 25), enriching demo data (Phase 26), adding guided tour (Phase 27), and completing onboarding documentation (Phase 28).

## Phases

### Phase 24: Visual Consistency

**Goal**: All tables and demo pages render correctly in both light and dark mode
**Depends on**: Nothing (foundation for v9)
**Requirements**: VIS-01, VIS-02, VIS-03, VIS-04
**Plans**: 2 plans

Plans:
- [x] 24-01-PLAN.md - Enhance design system .st-table with alternating rows and dark mode text
- [x] 24-02-PLAN.md - Migrate templates to .st-table and verify demo pages

**Success Criteria:**
1. Every table in the codebase uses .st-table or dark-mode-aware classes (no inline styles)
2. User can toggle dark mode on any demo page without visual artifacts
3. Data tables display alternating row colors in both light and dark mode

### Phase 25: Landing Page

**Goal**: Visitors immediately understand what SpecTrace does and why they need it
**Depends on**: Phase 24 (visual consistency applies to landing page)
**Requirements**: LAND-01, LAND-02, LAND-03, LAND-04
**Plans**: 1 plan

Plans:
- [x] 25-01-PLAN.md - Add value proposition, feature highlight cards, verify dark mode

**Success Criteria:**
1. Visitor reads one-line value proposition and understands SpecTrace's purpose
2. Visitor sees 3-4 key features with icons that explain capabilities at a glance
3. Visitor can click feature highlights to navigate to relevant demos
4. Landing page renders correctly in dark mode

### Phase 26: Demo Data & Hub

**Goal**: Demo shows realistic scenarios that mirror production usage patterns
**Depends on**: Phase 25 (landing page links to demos)
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04
**Plans**: 2 plans

Plans:
- [x] 26-01-PLAN.md - Remove unused YAML fields, create 3-level sample specs
- [x] 26-02-PLAN.md - Create sample tests with mixed status, verify vendor scenarios

**Success Criteria:**
1. Demo Hub YAML files contain only used fields (no vestigial options/talking_points)
2. Sample requirements show 3+ level hierarchy (epic -> feature -> story pattern)
3. Dashboard displays mix of passing (green), failing (red), and untested (gray) requirements
4. Validation runs show realistic vendor scenarios (multiple vendors, varied outcomes)

### Phase 27: Guided Tour

**Goal**: New users can follow a step-by-step walkthrough of the SpecTrace workflow
**Depends on**: Phase 26 (tour uses demo data)
**Requirements**: DEMO-05, DEMO-06
**Plans**: 1 plan

Plans:
- [x] 27-01-PLAN.md - Add Driver.js tour to landing page and demo hub entry point

**Success Criteria:**
1. User can start guided tour from landing page
2. User can start guided tour from demo hub
3. Tour explains write specs -> link tests -> view dashboard workflow

### Phase 28: Onboarding Guide

**Goal**: New teams have clear documentation to integrate SpecTrace into their workflow
**Depends on**: Phase 26 (guide references demo data patterns)
**Requirements**: ONBD-01, ONBD-02, ONBD-03, ONBD-04
**Plans**: 1 plan

Plans:
- [x] 28-01-PLAN.md - Create getting started guide with progressive disclosure, copy-paste examples, and landing page link

**Success Criteria:**
1. User can access getting started guide from landing page
2. Guide explains what SpecTrace is, how to add specs, and how to link tests
3. Guide includes copy-paste code examples for pytest markers
4. Guide shows screenshot of expected dashboard after setup

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 24. Visual Consistency | 2/2 | Complete | 2026-02-03 |
| 25. Landing Page | 1/1 | Complete | 2026-02-03 |
| 26. Demo Data & Hub | 2/2 | Complete | 2026-02-03 |
| 27. Guided Tour | 1/1 | Complete | 2026-02-03 |
| 28. Onboarding Guide | 1/1 | Complete | 2026-02-03 |

---

## Milestone Summary

**Key Decisions:**
- Design system uses semantic CSS variables that auto-flip in dark mode
- Landing page value proposition: "See which requirements are verified by passing tests"
- Driver.js loaded from CDN (no npm install) for minimal footprint
- SessionStorage pattern for cross-page tour triggering
- Progressive disclosure structure for getting started guide: What → Workflow → Steps → Next Steps
- Alpine.js x-data pattern for copy-to-clipboard (consistent with spectrace_overview.html)

**Issues Resolved:**
- Dark mode table text readability (Phase 24)
- Value proposition clarity for engineering leads (Phase 25)
- Demo data realism with 3-level hierarchy (Phase 26)
- New user workflow understanding via guided tour (Phase 27)
- Onboarding documentation completeness (Phase 28)

**Issues Deferred:**
- Video tutorials (text/interactive demos sufficient for v9)
- Analytics tracking (privacy concerns, not needed for evaluation)
- Historical coverage trends chart (moved to v10+)

**Technical Debt Incurred:**
- list_demos.py still has vestigial talking_points handling code (no demos use it)
- Sample tests use `assert True` placeholder logic (acceptable for demo data)

---

*Archived: 2026-02-03*
*For current project status, see .planning/ROADMAP.md*
