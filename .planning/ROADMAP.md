# Roadmap: SpecTrace v7 — UI Polish & API Documentation

**Created:** 2026-01-25
**Phases:** 15-18 (4 phases)

---

## Phase 15: Dark Mode Fixes

**Goal:** Fix dark mode styling across all custom admin views.

**Requirements:** DARK-01, DARK-02, DARK-03, DARK-04

**Scope:**
- Audit custom templates for missing dark mode classes
- Add `dark:` Tailwind variants to all custom views
- Ensure consistency with django-unfold theme

**Key files:**
- `templates/admin/requirements/validation_runs.html`
- `templates/admin/requirements/validation_run_detail.html`
- `templates/admin/requirements/validation_run_compare.html`
- `templates/admin/requirements/impact_analysis.html`

---

## Phase 16: UX Improvements

**Goal:** Improve navigation flow and add loading states for async operations.

**Requirements:** NAV-01, NAV-02, LOAD-01, LOAD-02

**Scope:**
- Add breadcrumb navigation to detail views
- Add "back to list" links
- Add loading spinners for form submissions
- Add loading state for comparison view

**Key files:**
- Detail view templates
- Alpine.js components for loading states

---

## Phase 17: Validation Filtering

**Goal:** Add advanced filtering to validation runs list with URL persistence.

**Requirements:** FILTER-01, FILTER-02, FILTER-03

**Scope:**
- Date range picker (start/end date inputs)
- Requirement ID filter dropdown
- Store filters in URL query params
- Restore filters from URL on page load

**Key files:**
- `templates/admin/requirements/validation_runs.html`
- `requirements/views.py` (validation_run_list_view)

---

## Phase 18: OpenAPI Documentation

**Goal:** Generate and serve OpenAPI documentation from msgspec Structs.

**Requirements:** DOCS-01, DOCS-02, DOCS-03

**Scope:**
- Generate OpenAPI 3.1 spec from existing msgspec Structs
- Serve spec at `/api/openapi.json`
- Add Swagger UI at `/api/docs/`
- Add ReDoc at `/api/redoc/` (optional)

**Note:** Another agent has started work on msgspec → OpenAPI generation.

**Key files:**
- `requirements/api.py`
- `spectrace/urls.py`
- New: `requirements/openapi.py`

---

## Phase Summary

| Phase | Name | Requirements | Focus |
|-------|------|--------------|-------|
| 15 | Dark Mode Fixes | DARK-01–04 | Template theming |
| 16 | UX Improvements | NAV-01–02, LOAD-01–02 | Navigation & loading |
| 17 | Validation Filtering | FILTER-01–03 | List filtering |
| 18 | OpenAPI Documentation | DOCS-01–03 | API docs |

**Total:** 4 phases, 14 requirements

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| msgspec for OpenAPI | Already using msgspec Structs, generate spec from existing types |
| Dark mode first | Quick wins, visible improvement |
| URL-based filter persistence | Shareable links, browser back/forward works |
| Swagger UI via CDN | No extra dependencies, always up to date |

---
*Created: 2026-01-25*
