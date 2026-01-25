# Requirements: SpecTrace v7 — UI Polish & API Documentation

**Defined:** 2026-01-25
**Core Value:** PMs can see, at any moment, which requirements are verified by passing tests

## Goal

Improve validation runs UX, add OpenAPI documentation, and fix dark mode consistency across custom views.

---

## Validation Runs Filtering

- [ ] **FILTER-01**: Date range filter on validation runs list
- [ ] **FILTER-02**: Filter by specific requirement ID
- [ ] **FILTER-03**: Persist filters across navigation (URL params)

## OpenAPI Documentation

- [ ] **DOCS-01**: Generate OpenAPI spec from msgspec Structs
- [ ] **DOCS-02**: Serve OpenAPI JSON at `/api/openapi.json`
- [ ] **DOCS-03**: Add Swagger UI / ReDoc at `/api/docs/`

## Dark Mode Consistency

- [ ] **DARK-01**: Fix validation runs list page dark mode
- [ ] **DARK-02**: Fix validation run detail page dark mode
- [ ] **DARK-03**: Fix validation run comparison page dark mode
- [ ] **DARK-04**: Fix impact analysis page dark mode

## Navigation & Loading

- [ ] **NAV-01**: Add breadcrumb navigation to detail views
- [ ] **NAV-02**: Add "back to list" links on detail pages
- [ ] **LOAD-01**: Add loading spinner for impact analysis form
- [ ] **LOAD-02**: Add loading state for validation run comparison

---

## Traceability

| Requirement | Phase | Status | Outcome |
|-------------|-------|--------|---------|
| FILTER-01 | TBD | Pending | — |
| FILTER-02 | TBD | Pending | — |
| FILTER-03 | TBD | Pending | — |
| DOCS-01 | TBD | Pending | — |
| DOCS-02 | TBD | Pending | — |
| DOCS-03 | TBD | Pending | — |
| DARK-01 | TBD | Pending | — |
| DARK-02 | TBD | Pending | — |
| DARK-03 | TBD | Pending | — |
| DARK-04 | TBD | Pending | — |
| NAV-01 | TBD | Pending | — |
| NAV-02 | TBD | Pending | — |
| LOAD-01 | TBD | Pending | — |
| LOAD-02 | TBD | Pending | — |

**Total:** 14 requirements

## Out of Scope

| Feature | Reason |
|---------|--------|
| GraphQL API | REST + OpenAPI sufficient |
| Real-time updates | Polling acceptable for v7 |
| API versioning | Single version for now |

---
*Created: 2026-01-25*
