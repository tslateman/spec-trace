# Project Research Summary

**Project:** SpecTrace - Requirements Traceability System (v3: Integration Health Checks)
**Domain:** Requirements Traceability / Spec-to-Test Management
**Researched:** 2026-01-19 (Updated 2026-01-21 for Integration Health Checks)
**Confidence:** HIGH

## Executive Summary

SpecTrace is a code-native requirements traceability system that stores markdown specs in the codebase and links them to pytest tests via decorators. The recommended approach is a Django 5.2 LTS monolith with a pipeline architecture: Spec Parser extracts requirements from markdown, Test Collector harvests pytest markers, CI Aggregator ingests test results, and a Django dashboard (enhanced with Unfold + HTMX) surfaces the traceability matrix. This is a well-trodden path with mature, production-ready components.

**NEW (v3 Milestone):** Integration health checks extend this architecture with monitoring for external integrations (Linear API, SLO platforms, CI/CD webhooks). The recommended pattern uses dataclass-based domain objects for check results with Django model persistence, following the Repository pattern to separate health check logic from storage. This aligns with SpecTrace's existing architecture where `status.py` separates computation from persistence. Implementation requires minimal dependencies: `django-health-check` framework patterns, standard library `dataclasses`, and the existing `requests` library.

The key architectural insight is that SpecTrace must build the foundation (database schema, spec parsing, pytest integration) before the visible dashboard. The temptation will be to build the dashboard first, but without reliable data pipelines, the dashboard will show garbage. Build in pipeline order: specs -> tests -> results -> display. **For health checks specifically:** Domain objects and security design must precede API implementation—rate limiting and timeout handling are day-one design decisions, not post-launch additions.

The critical risk is **Hierarchical ID Fragility**: using position-based IDs like REQ-1.2.3 that break when specs are reorganized. Use immutable sequential IDs (SPEC-0042) with hierarchy expressed in folder structure and metadata. **For health checks:** Primary risks are **rate limiting external APIs** (Linear has strict 5,000 req/hour limits), **Django async/timeout deadlocks** that can hang the entire process, and **security exposure** through verbose error responses. Mitigation requires caching results (5-15 min TTL), synchronous HTTP with aggressive timeouts (2-5s), and minimal response formats.

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
- **django-health-check 3.20.8** (NEW): Health check framework patterns - pluggable backends, official Django solution
- **requests 2.32.5**: HTTP/GraphQL testing - already in stack for Linear client, handles retry strategy
- **dataclasses (stdlib)**: Frozen dataclasses for health check results - immutable, no Pydantic overhead

**What to avoid:**
- django-mppt (officially unmaintained)
- Celery (overkill; use Huey if needed, not needed for health checks)
- React/Vue SPA (violates single-repo requirement)
- Custom admin from scratch (months of work; Unfold is 90% there)
- **Pydantic for health checks** (NEW): Unnecessary for internal results, use frozen dataclasses
- **httpx/aiohttp for health checks** (NEW): Django async/sync bridging causes deadlocks, use synchronous requests

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
- **Connection testing endpoints** (NEW): POST endpoints to test Linear API, SLO platforms on-demand
- **Granular diagnostic checks** (NEW): Separate auth, reachability, permissions checks with individual status
- **Dashboard health status display** (NEW): Show latest health for each integration with timestamps
- **Error details in responses** (NEW): API endpoints return structured error information for debugging

**Should have (competitive differentiators):**
- Markdown-native specs living in the codebase
- Git integration for spec history (no custom versioning)
- Coverage gap highlighting (requirements without tests)
- Bidirectional traceability (requirement->tests AND test->requirements)
- CI integration hooks for auto-status updates
- **Historical health tracking** (NEW): Persist check results for trend analysis and debugging
- **Admin interface for health history** (NEW): View past health check results in Django admin
- **Manual refresh from dashboard** (NEW): Trigger health checks from admin UI with rate limit warnings
- **Multi-check aggregation** (NEW): Roll up individual checks into overall integration status (healthy/degraded/failure)

**Defer (v2+):**
- Real-time CI updates (polling/refresh acceptable for MVP)
- Historical coverage trends visualization
- Impact analysis (which tests affected by spec changes)
- Bulk import/export
- Multi-stakeholder views (single view serves all for MVP)
- **Automated periodic health checks** (NEW): Background jobs running checks on schedule (requires Celery)
- **Alerting on health failures** (NEW): Proactive notifications when integrations degrade
- **Prometheus/Datadog integration** (NEW): Export health metrics to external monitoring systems
- **Circuit breaker pattern** (NEW): Auto-disable checks after repeated failures (optimization phase)

**Anti-features (do not build):**
- Full ALM/PLM suite (scope creep)
- Built-in test execution (reinventing pytest/CI)
- Electronic signatures (regulated industry complexity)
- Complex approval workflows (enterprise overhead)
- AI requirement generation (gimmick)

### Architecture Approach

SpecTrace follows a pipeline architecture with distinct processing stages feeding a central PostgreSQL store, surfaced through a read-only Django dashboard. Data flows: Spec Parser extracts requirements from markdown files -> Test Collector harvests pytest markers -> CI Aggregator ingests JUnit XML results -> Traceability Engine computes coverage status -> Dashboard displays matrix.

**NEW (Health Checks):** The health check architecture extends SpecTrace's existing separation pattern where domain logic lives independently from persistence. Domain objects (`VerificationCheck`, `TestConnectionResult`) are pure Python dataclasses with no Django dependencies. Health checker classes wrap external clients (LinearClient) and return domain objects. The Repository pattern mediates persistence to Django models (`IntegrationHealth`, `IntegrationHealthCheck`), allowing API endpoints to optionally persist results or return ephemeral responses.

**Major components:**
1. **Spec Parser** - Parse markdown specs with YAML frontmatter into requirement records
2. **Test Collector** - Pytest plugin using `pytest_collection_finish` hook to extract markers
3. **CI Aggregator** - Webhook-based ingestion of JUnit XML with idempotent processing
4. **Traceability Engine** - Query-based coverage computation and gap analysis
5. **Django Dashboard** - Server-side rendered views with HTMX interactivity
6. **CLI Tool** - Developer interface for parse, collect, status, sync commands
7. **Health Check Domain Objects** (NEW) - Frozen dataclasses for check results, aggregation logic, status enums
8. **Health Checker Classes** (NEW) - LinearHealthChecker, SLOHealthChecker with test_connection() methods
9. **Health Check Repository** (NEW) - save_result(), get_latest_result() abstracting Django ORM

**Key patterns to follow:**
- Event sourcing for CI results (immutable records, derive current status)
- Idempotent webhook processing (unique event IDs)
- Hierarchical requirement IDs in format REQ-{FEATURE}-{NUMBER}
- Separate collection from execution (pytest --collect-only)
- **Domain objects separate from persistence** (NEW): Health check logic independent of Django ORM
- **Repository pattern for persistence** (NEW): Abstract database operations, enable testing without DB
- **Three-level aggregation hierarchy** (NEW): Individual checks → integration health → system-wide status

### Critical Pitfalls

1. **Hierarchical ID Fragility** - Position-based IDs (REQ-1.2.3) break on restructure. Use immutable sequential IDs (SPEC-0042); express hierarchy in folder structure and metadata, not the ID. Address in Phase 1.

2. **Specification Drift** - Specs become out of sync with code. Enforce bi-directional traceability, surface orphan specs/tests, include spec owners in code review. Address in Phase 2 and ongoing.

3. **False Confidence from Green Dashboards** - High coverage % but tests don't actually verify requirements. Distinguish "linked" from "verified", surface test quality signals, don't make coverage the KPI. Address in Phase 3.

4. **Test Result Sync Race Conditions** - Dashboard shows stale/incorrect results due to transaction races. Use `transaction.on_commit()`, idempotent updates with timestamps, event sourcing. Address in Phase 3.

5. **Manual Traceability Burden** - Decorators get skipped if tedious. Enforce decorators in CI, provide IDE autocomplete, make it required from day one. Address in Phase 2.

6. **Rate Limiting External APIs Without Awareness** (NEW) - Linear has strict 5,000 req/hour limits. Naive polling every 30s consumes quotas, causing real user requests to fail. Cache results with 5-15 minute TTL, use webhook push where possible, track remaining quota from response headers (`X-RateLimit-Remaining`). Address in Phase 6 (Health Check API).

7. **Django Async/Timeout Deadlocks** (NEW) - Django 4.2+ with asgiref 3.8+ deadlocks when HTTP requests timeout if using `async_to_sync()` with external API calls. Entire process hangs. Use synchronous requests library with aggressive 2-5s timeouts, avoid async_to_sync in views. Address in Phase 5 (Health Check Foundation).

8. **Health Check Security Exposure** (NEW) - Verbose error responses leak API keys, internal URLs, stack traces. Return minimal `{"status": "healthy/degraded/unhealthy", "timestamp": "..."}` only. Separate public `/health` from authenticated `/admin/health/detailed`. Sanitize error messages. Address in Phase 6 (Health Check API).

9. **Database Connection Pool Exhaustion** (NEW) - Health checks querying database consume connections, paradoxically causing database issues. Use connection-less checks or reserve separate pool capacity. Implement 2-5s connection timeout, circuit breaker after 3 failures. Address in Phase 6 (Health Check API).

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

### Phase 5: Health Check Foundation (NEW - Domain Objects & Security Design)
**Rationale:** Pure Python domain objects enable testing without database. Security design (response format, auth strategy) must precede API implementation to avoid retrofitting.
**Delivers:**
- `VerificationCheck` and `TestConnectionResult` dataclasses
- `HealthChecker` base class
- `LinearHealthChecker` implementation (auth, reachability, permissions checks)
- `IntegrationHealth` and `IntegrationHealthCheck` models + migrations
- `HealthCheckRepository` with save_result(), get_latest_result()
- Response format design (minimal, sanitized)
- Webhook authentication strategy (HMAC or API key)
**Addresses:** Foundation for connection testing, granular diagnostics
**Avoids:** Async/timeout deadlocks (design synchronous from start), Security exposure (sanitized responses designed upfront)
**Stack:** dataclasses (stdlib), requests 2.32.5

### Phase 6: Health Check API & Dashboard (NEW - Endpoints & UI)
**Rationale:** With domain objects tested and persistence working, API endpoints become thin controllers. Rate limiting and timeout handling implemented here.
**Delivers:**
- POST /api/integrations/linear/test/ endpoint
- GET /api/integrations/{name}/health/ endpoint
- URL routing configuration
- Rate limit caching (5-15 minute TTL)
- Aggressive timeout configuration (2-5 seconds)
- Dashboard context extension (health status variables)
- Status badge display in dashboard
- Last checked timestamps, stale cache indicators
- Manual refresh button with rate limit warning
- IntegrationHealthAdmin for historical views
**Addresses:** Connection testing endpoints, dashboard health display, error details, historical tracking
**Avoids:** Rate limiting (caching from start), Connection exhaustion (connection-less checks), Stale cache confusion (timestamps and indicators)
**Stack:** Django REST endpoints, django-unfold dashboard patterns

### Phase 7: Collaboration + Polish (PM Workflow)
**Rationale:** Only needed once core system works. Addresses adoption friction.
**Delivers:** Web-based spec editing (optional), granular file structure, PM-friendly workflows, export capabilities
**Addresses:** Bulk import/export, multi-stakeholder views
**Avoids:** Merge conflict hell (granular files), PM-Engineer workflow mismatch (collaborative features)

### Phase Ordering Rationale

- **Foundation before features:** Database schema and ID scheme are irreversible decisions. The temptation to "just build the dashboard" leads to data model problems discovered too late.
- **Data pipelines before display:** Each phase delivers a complete data pipeline. Phase 1 = specs in DB. Phase 2 = tests linked. Phase 3 = visualize what exists. Phase 4 = automate updates.
- **Defer CI complexity:** Webhook handling, async processing, and race conditions are the hardest problems. Manual import works for MVP demos; automation comes after core value is proven.
- **Health checks after core features:** Integration health monitoring builds on existing architecture. Domain objects and security first (Phase 5), then API and UI (Phase 6).
- **Security before exposure (health checks):** Response format and authentication designed before implementing HTTP endpoints prevents security retrofitting.
- **Group by architecture component:** Each phase maps roughly to one major component from the architecture research.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 4 (CI Integration):** Webhook reliability, JUnit XML variations across CI systems, async processing patterns. Consider `/gsd:research-phase` before detailed planning.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Foundation):** Django project setup, model design are well-documented
- **Phase 2 (Test Integration):** pytest plugin patterns are well-documented in official docs
- **Phase 3 (Dashboard):** django-unfold has extensive documentation and examples
- **Phase 5-6 (Health Checks):** Dataclass patterns, Repository pattern, Django API endpoints all verified with official sources. Existing SpecTrace codebase demonstrates compatible patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified from PyPI/official docs on 2026-01-19, health check additions verified 2026-01-21 |
| Features | HIGH | Multiple authoritative sources (Jama, DOORS, Doorstop, industry analysis), health check patterns from django-health-check, Azure, Spring Boot |
| Architecture | HIGH | Standard patterns from pytest docs, Django docs, established traceability concepts. Health check Repository pattern verified in Architecture Patterns with Python, existing SpecTrace code shows separation pattern |
| Pitfalls | HIGH | Multiple domain-specific sources, common patterns verified. Health check pitfalls verified with Linear API docs, Django forum (2025 deadlock reports), Azure/Spring Boot security guidance |

**Overall confidence:** HIGH

All research files cite official documentation, PyPI packages, and established industry sources. The domain of requirements traceability is mature with well-documented patterns. The specific technology choices (Django 5.2 LTS, pytest markers, django-unfold) are production-proven. Health check architecture patterns validated with current 2025-2026 sources.

### Gaps to Address

- **CI system variations:** JUnit XML parsing may need adjustment for different CI systems (GitHub Actions vs GitLab CI vs Jenkins). Validate during Phase 4.
- **Scale testing:** Performance research is theoretical; validate dashboard query performance with realistic data volumes during Phase 3.
- **Spec granularity guidance:** Research identifies the risk but doesn't prescribe exact granularity. Develop guidelines during Phase 1 based on actual spec content.
- **Health check cache TTL tuning:** Research recommends 5-15 minutes, but exact value should be tuned based on actual Linear API usage patterns during Phase 6.

## Sources

### Primary (HIGH confidence)
- [Django 5.2 Release Notes](https://docs.djangoproject.com/en/6.0/releases/5.2/)
- [pytest markers documentation](https://docs.pytest.org/en/stable/how-to/mark.html)
- [pytest hooks documentation](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html)
- [django-unfold PyPI](https://pypi.org/project/django-unfold/)
- [django-treebeard PyPI](https://pypi.org/project/django-treebeard/)
- [python-frontmatter PyPI](https://pypi.org/project/python-frontmatter/)
- [Doorstop GitHub](https://github.com/doorstop-dev/doorstop)
- **[django-health-check 3.20.8 (PyPI)](https://pypi.org/project/django-health-check/)** (NEW) - Health check framework patterns
- **[Linear API Rate Limiting](https://developers.linear.app/docs/graphql/working-with-the-graphql-api/rate-limiting)** (NEW) - Rate limit specifics
- **[Django Async Deadlock Issues](https://forum.djangoproject.com/t/django-4-2-16-daphne-4-1-2-http-requests-timeout-result-main-thread-deadlock/38835)** (NEW) - Async/timeout pitfall (2025)
- **[Cosmic Python: Repository Pattern with Django](https://www.cosmicpython.com/book/appendix_django.html)** (NEW) - Architecture pattern
- **[Azure Health Endpoint Monitoring](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring)** (NEW) - Security and design patterns

### Secondary (MEDIUM confidence)
- [Inflectra - Best Requirements Traceability Software 2026](https://www.inflectra.com/tools/requirements-management/10-best-requirements-traceability-tools)
- [Jama Software - Requirements Traceability](https://www.jamasoftware.com/requirements-management-guide/requirements-traceability/)
- [ByteByteGo: Polling vs Webhooks](https://blog.bytebytego.com/p/ep100-polling-vs-webhooks)
- [Haki Benita: Django Admin Paginator](https://hakibenita.com/optimizing-the-django-admin-paginator)
- **[Medium: Production-Grade Health Check in Django](https://medium.com/@iman.rameshni/django-health-check-89fb6ad39b0c)** (NEW) - Best practices
- **[Microservices Health Check API Pattern](https://microservices.io/patterns/observability/health-check-api.html)** (NEW) - Aggregation patterns

### Tertiary (LOW confidence)
- [HackerNoon: Misleading Test Coverage](https://hackernoon.com/misleading-test-coverage-and-how-to-avoid-false-confidence) - general patterns, apply with judgment

---
*Research completed: 2026-01-19 (Updated 2026-01-21 for Integration Health Checks)*
*Ready for roadmap: yes*
