# Project Research Summary

**Project:** SpecTrace - Requirements Traceability System
**Domain:** Requirements Traceability / Spec-to-Test Management
**Researched:** 2026-01-19
**Confidence:** HIGH

## Executive Summary

SpecTrace is a code-native requirements traceability system that stores markdown specs in the codebase and links them to pytest tests via decorators. The recommended approach is a Django 5.2 LTS monolith with a pipeline architecture: Spec Parser extracts requirements from markdown, Test Collector harvests pytest markers, CI Aggregator ingests test results, and a Django dashboard (enhanced with Unfold + HTMX) surfaces the traceability matrix. This is a well-trodden path with mature, production-ready components.

The key architectural insight is that SpecTrace must build the foundation (database schema, spec parsing, pytest integration) before the visible dashboard. The temptation will be to build the dashboard first, but without reliable data pipelines, the dashboard will show garbage. Build in pipeline order: specs -> tests -> results -> display.

The critical risk is **Hierarchical ID Fragility**: using position-based IDs like REQ-1.2.3 that break when specs are reorganized. This is a day-one design decision that cannot be retrofitted. Use immutable sequential IDs (SPEC-0042) with hierarchy expressed in folder structure and metadata, not in the ID itself. Secondary risks include specification drift (specs becoming out of sync with code) and false confidence from green dashboards (tests that link to requirements but don't actually verify them).

## Key Findings

### Recommended Stack

Django 5.2 LTS provides the foundation with mature admin capabilities, ORM, and a single-repo architecture. The admin is enhanced with django-unfold for modern TailwindCSS styling and django-htmx for interactivity without SPA complexity. PostgreSQL 14+ is recommended for concurrent writes, JSONB metadata storage, and full-text search. Pytest 9.x with custom markers handles requirement linking idiomatically.

**Core technologies:**
- **Django 5.2 LTS**: Web framework - mature admin, ORM, LTS until April 2028
- **PostgreSQL 14+**: Database - concurrent writes, JSONB, full-text search
- **django-unfold + django-htmx**: Dashboard - modern UI without SPA complexity
- **pytest 9.x + custom markers**: Test linking - idiomatic, validated at collection
- **python-frontmatter + Python-Markdown**: Spec parsing - YAML metadata + rendered content
- **django-treebeard (materialized path)**: Hierarchy - balanced read/write, actively maintained

**What to avoid:**
- django-mptt (officially unmaintained)
- Celery (overkill; use Huey if needed)
- React/Vue SPA (violates single-repo requirement)
- Custom admin from scratch (months of work; Unfold is 90% there)

### Expected Features

**Must have (table stakes):**
- Unique requirement IDs with hierarchy support
- Test-to-requirement linking via pytest decorators
- Verification status per requirement (Pass/Fail/Untested)
- Coverage metrics (% requirements with passing tests)
- Basic traceability matrix (requirements vs tests grid)
- Search and filter by ID, text, status, tag
- Test execution history
- Dashboard summary view

**Should have (competitive differentiators):**
- Markdown-native specs living in the codebase
- Git integration for spec history (no custom versioning)
- Coverage gap highlighting (requirements without tests)
- Bidirectional traceability (requirement->tests AND test->requirements)
- CI integration hooks for auto-status updates

**Defer (v2+):**
- Real-time CI updates (polling/refresh acceptable for MVP)
- Historical coverage trends visualization
- Impact analysis (which tests affected by spec changes)
- Bulk import/export
- Multi-stakeholder views (single view serves all for MVP)

**Anti-features (do not build):**
- Full ALM/PLM suite (scope creep)
- Built-in test execution (reinventing pytest/CI)
- Electronic signatures (regulated industry complexity)
- Complex approval workflows (enterprise overhead)
- AI requirement generation (gimmick)

### Architecture Approach

SpecTrace follows a pipeline architecture with distinct processing stages feeding a central PostgreSQL store, surfaced through a read-only Django dashboard. Data flows: Spec Parser extracts requirements from markdown files -> Test Collector harvests pytest markers -> CI Aggregator ingests JUnit XML results -> Traceability Engine computes coverage status -> Dashboard displays matrix.

**Major components:**
1. **Spec Parser** - Parse markdown specs with YAML frontmatter into requirement records
2. **Test Collector** - Pytest plugin using `pytest_collection_finish` hook to extract markers
3. **CI Aggregator** - Webhook-based ingestion of JUnit XML with idempotent processing
4. **Traceability Engine** - Query-based coverage computation and gap analysis
5. **Django Dashboard** - Server-side rendered views with HTMX interactivity
6. **CLI Tool** - Developer interface for parse, collect, status, sync commands

**Key patterns to follow:**
- Event sourcing for CI results (immutable records, derive current status)
- Idempotent webhook processing (unique event IDs)
- Hierarchical requirement IDs in format REQ-{FEATURE}-{NUMBER}
- Separate collection from execution (pytest --collect-only)

### Critical Pitfalls

1. **Hierarchical ID Fragility** - Position-based IDs (REQ-1.2.3) break on restructure. Use immutable sequential IDs (SPEC-0042); express hierarchy in folder structure and metadata, not the ID. Address in Phase 1.

2. **Specification Drift** - Specs become out of sync with code. Enforce bi-directional traceability, surface orphan specs/tests, include spec owners in code review. Address in Phase 2 and ongoing.

3. **False Confidence from Green Dashboards** - High coverage % but tests don't actually verify requirements. Distinguish "linked" from "verified", surface test quality signals, don't make coverage the KPI. Address in Phase 3.

4. **Test Result Sync Race Conditions** - Dashboard shows stale/incorrect results due to transaction races. Use `transaction.on_commit()`, idempotent updates with timestamps, event sourcing. Address in Phase 3.

5. **Manual Traceability Burden** - Decorators get skipped if tedious. Enforce decorators in CI, provide IDE autocomplete, make it required from day one. Address in Phase 2.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation (Data Model + Spec Parsing)
**Rationale:** Everything depends on the data model and requirement ID scheme. Get this wrong and you rebuild everything. Spec parsing is the first data source.
**Delivers:** Django project, database schema, spec file format, requirement parser
**Addresses:** Requirement IDs, hierarchy, text storage from table stakes
**Avoids:** Hierarchical ID Fragility (design immutable IDs), Markdown flavor inconsistency (standardize on GFM)
**Stack:** Django 5.2, PostgreSQL, python-frontmatter, django-treebeard

### Phase 2: Test Integration (Pytest Plugin + Collection)
**Rationale:** Requires Phase 1 (requirements must exist before tests can link). This creates the second data pipeline.
**Delivers:** pytest plugin with @pytest.mark.requirement decorator, test collection, CLI parse/collect commands
**Addresses:** Test-to-requirement linking from table stakes
**Avoids:** Manual traceability burden (enforce in CI from start), Orphan specs/tests (bidirectional validation)
**Stack:** pytest 9.x, pytest-django, pytest-json-report

### Phase 3: Dashboard (Traceability Matrix + Metrics)
**Rationale:** Requires Phase 1+2 (need data to display). This is the PM-facing value delivery.
**Delivers:** Traceability matrix view, coverage dashboard, requirement detail views, search/filter
**Addresses:** Verification status, coverage metrics, traceability matrix, dashboard summary
**Avoids:** Dashboard performance degradation (cursor pagination, denormalized status), False confidence (honest metrics)
**Stack:** django-unfold, django-htmx

### Phase 4: CI Integration (Automated Status Updates)
**Rationale:** Most complex, most optional for MVP. Can demo with manual result import first.
**Delivers:** Webhook endpoint, JUnit XML parsing, automated status updates, test history
**Addresses:** Test execution history, real-time verification status
**Avoids:** Race conditions (transaction.on_commit, idempotent processing, event sourcing)
**Stack:** Webhook handlers, junitparser, possibly Huey for async

### Phase 5: Collaboration + Polish (PM Workflow)
**Rationale:** Only needed once core system works. Addresses adoption friction.
**Delivers:** Web-based spec editing (optional), granular file structure, PM-friendly workflows, export capabilities
**Addresses:** Bulk import/export, multi-stakeholder views
**Avoids:** Merge conflict hell (granular files), PM-Engineer workflow mismatch (collaborative features)

### Phase Ordering Rationale

- **Foundation before features:** Database schema and ID scheme are irreversible decisions. The temptation to "just build the dashboard" leads to data model problems discovered too late.
- **Data pipelines before display:** Each phase delivers a complete data pipeline. Phase 1 = specs in DB. Phase 2 = tests linked. Phase 3 = visualize what exists. Phase 4 = automate updates.
- **Defer CI complexity:** Webhook handling, async processing, and race conditions are the hardest problems. Manual import works for MVP demos; automation comes after core value is proven.
- **Group by architecture component:** Each phase maps roughly to one major component from the architecture research.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (CI Integration):** Webhook reliability, JUnit XML variations across CI systems, async processing patterns. Consider `/gsd:research-phase` before detailed planning.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Django project setup, model design are well-documented
- **Phase 2 (Test Integration):** pytest plugin patterns are well-documented in official docs
- **Phase 3 (Dashboard):** django-unfold has extensive documentation and examples

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified from PyPI/official docs on 2026-01-19 |
| Features | HIGH | Multiple authoritative sources (Jama, DOORS, Doorstop, industry analysis) |
| Architecture | HIGH | Standard patterns from pytest docs, Django docs, established traceability concepts |
| Pitfalls | HIGH | Multiple domain-specific sources, common patterns verified across literature |

**Overall confidence:** HIGH

All research files cite official documentation, PyPI packages, and established industry sources. The domain of requirements traceability is mature with well-documented patterns. The specific technology choices (Django 5.2 LTS, pytest markers, django-unfold) are production-proven.

### Gaps to Address

- **CI system variations:** JUnit XML parsing may need adjustment for different CI systems (GitHub Actions vs GitLab CI vs Jenkins). Validate during Phase 4.
- **Scale testing:** Performance research is theoretical; validate dashboard query performance with realistic data volumes during Phase 3.
- **Spec granularity guidance:** Research identifies the risk but doesn't prescribe exact granularity. Develop guidelines during Phase 1 based on actual spec content.

## Sources

### Primary (HIGH confidence)
- [Django 5.2 Release Notes](https://docs.djangoproject.com/en/6.0/releases/5.2/)
- [pytest markers documentation](https://docs.pytest.org/en/stable/how-to/mark.html)
- [pytest hooks documentation](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html)
- [django-unfold PyPI](https://pypi.org/project/django-unfold/)
- [django-treebeard PyPI](https://pypi.org/project/django-treebeard/)
- [python-frontmatter PyPI](https://pypi.org/project/python-frontmatter/)
- [Doorstop GitHub](https://github.com/doorstop-dev/doorstop)

### Secondary (MEDIUM confidence)
- [Inflectra - Best Requirements Traceability Software 2026](https://www.inflectra.com/tools/requirements-management/10-best-requirements-traceability-tools)
- [Jama Software - Requirements Traceability](https://www.jamasoftware.com/requirements-management-guide/requirements-traceability/)
- [ByteByteGo: Polling vs Webhooks](https://blog.bytebytego.com/p/ep100-polling-vs-webhooks)
- [Haki Benita: Django Admin Paginator](https://hakibenita.com/optimizing-the-django-admin-paginator)

### Tertiary (LOW confidence)
- [HackerNoon: Misleading Test Coverage](https://hackernoon.com/misleading-test-coverage-and-how-to-avoid-false-confidence) - general patterns, apply with judgment

---
*Research completed: 2026-01-19*
*Ready for roadmap: yes*
