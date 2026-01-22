# Project Milestones: SpecTrace

## v1 MVP (Shipped: 2026-01-21)

**Delivered:** Requirements traceability system connecting product specs to verified tests with Django dashboard showing pass/fail/untested status.

**Phases completed:** 1-4 (6 plans total)

**Key accomplishments:**

- Markdown spec parsing with YAML frontmatter and treebeard hierarchy
- pytest @requirement decorator with extract_links command
- JUnit XML import with verification status computation
- Django-unfold dashboard with metrics banner and hierarchical tree view
- Bidirectional navigation (requirement ↔ tests)
- Link validation command for CI/CD drift detection
- REST API for external system integration
- Linear integration for issue sync

**Stats:**

- 87 files created/modified
- 5,201 lines of Python
- 4 phases, 6 plans
- 3 days from start to ship (2026-01-19 → 2026-01-21)

**Git range:** `3608c1e` (feat: django setup) → `72310b2` (docs: state update)

**What's next:** v2 — Traceability matrix, impact analysis, CI webhooks

---

## v2 Traceability Matrix (Current)

**Goal:** Visual grid view showing which tests verify which requirements — enabling at-a-glance understanding of test coverage distribution and gaps.

**Phases:**

| Phase | Name | Status |
|-------|------|--------|
| 1 | Matrix Data Layer | Not Started |
| 2 | Matrix View | Not Started |
| 3 | Filtering & Navigation | Not Started |
| 4 | Export & Polish | Not Started |

**Key requirements:**
- MATRIX-01: Paginated grid (requirements × tests)
- MATRIX-02: Color-coded cells (pass/fail/untested/unlinked)
- MATRIX-03: Filtering by status, tags, hierarchy
- MATRIX-04: Dashboard tab integration
- MATRIX-05: Cell drill-down with details
- MATRIX-06: CSV export

**Technical approach:**
- Paginated grid (25-50 requirements per page)
- Horizontal scroll for test columns
- Dashboard tab in django-unfold admin

**Files:**
- `.planning/milestones/v2-REQUIREMENTS.md`
- `.planning/milestones/v2-ROADMAP.md`

---
