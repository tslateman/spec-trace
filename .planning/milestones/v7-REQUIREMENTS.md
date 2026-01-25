# Requirements Archive: SpecTrace v7 — UI Polish & API Documentation

**Defined:** 2026-01-25
**Completed:** 2026-01-25

## Goal

Improve validation runs UX, add OpenAPI documentation, and fix dark mode consistency across custom views.

---

## Validation Runs Filtering

- [x] **FILTER-01**: Date range filter on validation runs list
- [x] **FILTER-02**: Filter by specific requirement ID
- [x] **FILTER-03**: Persist filters across navigation (URL params)

## OpenAPI Documentation

- [x] **DOCS-01**: Generate OpenAPI spec from msgspec Structs
- [x] **DOCS-02**: Serve OpenAPI JSON at `/api/openapi.json`
- [x] **DOCS-03**: Add Swagger UI / ReDoc at `/api/docs/`

## Dark Mode Consistency

- [x] **DARK-01**: Fix validation runs list page dark mode
- [x] **DARK-02**: Fix validation run detail page dark mode
- [x] **DARK-03**: Fix validation run comparison page dark mode
- [x] **DARK-04**: Fix impact analysis page dark mode

## Navigation & Loading

- [x] **NAV-01**: Add breadcrumb navigation to detail views
- [x] **NAV-02**: Add "back to list" links on detail pages
- [x] **LOAD-01**: Add loading spinner for impact analysis form
- [x] **LOAD-02**: Add loading state for validation run comparison

---

## Traceability

| Requirement | Phase | Status | Outcome |
|-------------|-------|--------|---------|
| FILTER-01 | 17 | Complete | Validated |
| FILTER-02 | 17 | Complete | Validated |
| FILTER-03 | 17 | Complete | Validated |
| DOCS-01 | 18 | Complete | Validated |
| DOCS-02 | 18 | Complete | Validated |
| DOCS-03 | 18 | Complete | Validated |
| DARK-01 | 15 | Complete | Validated |
| DARK-02 | 15 | Complete | Validated |
| DARK-03 | 15 | Complete | Validated |
| DARK-04 | 15 | Complete | Validated |
| NAV-01 | 16 | Complete | Validated |
| NAV-02 | 16 | Complete | Validated |
| LOAD-01 | 16 | Complete | Validated |
| LOAD-02 | 16 | Complete | Validated |

**Total:** 14/14 requirements completed (100%)

## Out of Scope (Remained Out of Scope)

| Feature | Reason |
|---------|--------|
| GraphQL API | REST + OpenAPI sufficient |
| Real-time updates | Polling acceptable for v7 |
| API versioning | Single version for now |

---
*Archived: 2026-01-25*
