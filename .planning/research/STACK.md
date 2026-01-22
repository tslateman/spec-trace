# Technology Stack for SpecTrace

**Project:** SpecTrace - Requirements Traceability System
**Researched:** 2026-01-19 (Updated 2026-01-21 for Integration Health Checks)
**Overall Confidence:** HIGH (verified with official documentation and PyPI)

---

## Executive Summary

SpecTrace should use a Django 5.2 LTS stack with pytest 9.x for the testing framework. The architecture leverages Django's mature admin ecosystem (enhanced with Unfold) for the dashboard, pytest custom markers for requirement linking, and python-frontmatter for spec parsing. This is a well-trodden path with excellent documentation and battle-tested components.

**NEW (v3):** Integration health checks require minimal additions - only `django-health-check` framework. Use standard library dataclasses for result objects and the existing `requests` library for connection testing.

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **Django** | 5.2.x (LTS) | Web framework | LTS release (supported until April 2028), compound primary keys, production-ready. Released April 2025. | HIGH |
| **Python** | 3.12 or 3.13 | Runtime | Django 5.2 supports 3.10-3.14. Use 3.12 for stability or 3.13 for latest features. | HIGH |

**Why Django 5.2 LTS:**
- Long-term support until April 2028 means minimal upgrade pressure
- Mature admin interface that can be enhanced (not replaced)
- Single Python repo requirement fits Django's monolithic architecture
- Proven at scale for internal tools and dashboards

**Source:** [Django 5.2 Release Notes](https://docs.djangoproject.com/en/6.0/releases/5.2/)

---

### Database

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **PostgreSQL** | 14+ | Primary database | Better concurrent write handling, JSONB for metadata, full-text search for spec content. Django 5.2 requires PostgreSQL 14+. | HIGH |
| SQLite | (alternative) | Simple deployments | Acceptable for single-user/low-traffic. Easier backup (single file). Consider if < 10 concurrent users. | MEDIUM |

**Why PostgreSQL over SQLite for SpecTrace:**
1. **Concurrent writes** - Test results may be pushed from CI while PMs browse dashboard
2. **JSONB fields** - Store arbitrary spec metadata without schema changes
3. **Full-text search** - Search across spec content natively
4. **Scalability** - Consistent performance as requirements grow

**When SQLite is acceptable:**
- Side project / personal use
- Single CI pipeline, no concurrent test runs
- < 1000 requirements, < 100 tests

**Source:** [alldjango.com - SQLite in Production](https://alldjango.com/articles/definitive-guide-to-using-django-sqlite-in-production), [Django SQLite Benchmark](https://blog.pecar.me/django-sqlite-benchmark)

---

### Admin Dashboard

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **django-unfold** | 0.76.x | Admin theme | Modern TailwindCSS design, built-in dashboard widgets, HTMX integration, dark mode. Actively maintained. | HIGH |
| **django-htmx** | 1.27.x | HTMX integration | Dynamic updates without JavaScript, official Django+HTMX bridge | HIGH |

**Why django-unfold:**
- Built on standard `django.contrib.admin` (not a replacement)
- Dashboard support without complex Python class overrides
- Conditional fields, advanced filtering, command palette
- TailwindCSS + HTMX + Alpine.js = modern UX without SPA complexity
- Supports Django 4.2, 5.0, 5.1, 5.2, and 6.0

**Alternatives NOT recommended:**
- **Grappelli**: Older aesthetic, less modern features
- **Django JET**: Original abandoned, "Reboot" has smaller community
- **Custom React/Vue dashboard**: Overkill for internal tool, breaks single-repo simplicity

**Source:** [Django Admin Theme Roundup 2025](https://www.djangoproject.com/weblog/2025/apr/18/admin-theme-roundup/), [Unfold Admin](https://unfoldadmin.com/)

---

### Testing Framework (Pytest Integration)

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **pytest** | 9.0.x | Test runner | Industry standard, custom markers for requirement IDs, extensive plugin ecosystem | HIGH |
| **pytest-django** | 4.11.x | Django integration | Official Django support, supports Django 5.2, pytest 7+ | HIGH |
| **pytest-json-report** | 1.5.x | JSON output | Structured test results for dashboard consumption | HIGH |

**Why pytest custom markers for requirements:**
```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requirement(id): link test to requirement ID"
    )

# test_feature.py
@pytest.mark.requirement("REQ-001")
def test_user_can_login():
    ...
```

Pytest markers are the idiomatic way to attach metadata to tests. The marker data can be:
- Collected via `pytest_collection_modifyitems` hook
- Exported via pytest-json-report
- Consumed by Django dashboard

**Alternatives considered:**
- **pytest-requirements plugin**: Exists but unmaintained, simple marker approach is cleaner
- **Docstring parsing**: Fragile, harder to validate
- **External mapping file**: Separates test from requirement, easy to get out of sync

**Source:** [pytest markers documentation](https://docs.pytest.org/en/stable/example/markers.html), [pytest-json-report PyPI](https://pypi.org/project/pytest-json-report/)

---

### Spec/Markdown Parsing

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **python-frontmatter** | 1.1.x | YAML frontmatter | Parse requirement metadata from spec files | HIGH |
| **Python-Markdown** | 3.10.x | Markdown rendering | Render spec content for dashboard display, extension API | HIGH |

**Why python-frontmatter + Python-Markdown:**

Spec files will look like:
```markdown
---
id: REQ-001
title: User Authentication
priority: high
status: draft
---

# User Authentication

Users must be able to log in with email and password...
```

- **python-frontmatter** extracts the YAML metadata dict + content body
- **Python-Markdown** renders the body to HTML for dashboard display
- Both are production-stable, well-documented

**Alternative considered:**
- **markdown-it-py**: CommonMark compliant, faster, but Python-Markdown has richer extension ecosystem and is more widely used in Django projects

**Source:** [python-frontmatter PyPI](https://pypi.org/project/python-frontmatter/), [Python-Markdown docs](https://python-markdown.github.io/)

---

### Hierarchical Data (Spec Tree)

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **django-treebeard** | 4.8.x | Tree structure | Materialized path for spec hierarchy, supports all major databases | HIGH |

**Why django-treebeard:**
- Supports multiple tree implementations (nested sets, materialized path, adjacency list)
- **Materialized path** recommended for SpecTrace: balanced read/write performance
- Actively maintained (v4.8.0 released December 2025)
- Supports Django 4.2, 5.1, 5.2 and Python 3.10-3.13

**Why NOT django-mptt:**
- PyPI page explicitly states: "This project is currently unmaintained"
- Recommends django-tree-queries as alternative
- Nested sets have slow inserts (whole-table lock)

**Materialized path tradeoffs:**
- Reads: Fast (single query for subtree)
- Writes: Moderate (only update descendants, not whole table)
- Perfect for specs (read-heavy, occasional restructuring)

**Source:** [django-treebeard PyPI](https://pypi.org/project/django-treebeard/), [django-mptt PyPI](https://pypi.org/project/django-mppt/)

---

### Integration Health Monitoring (NEW in v3)

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **django-health-check** | 3.20.8 | Health check framework | Pluggable health check backend system, `/ht/` endpoint with HTML/JSON, actively maintained (Dec 2025). | HIGH |
| **requests** | 2.32.5 | HTTP/GraphQL testing | Already in stack. Handles both REST and GraphQL (Linear API). Built-in retry via HTTPAdapter. | HIGH |
| **dataclasses** | stdlib 3.12+ | Result objects | Frozen dataclasses for immutable health check results. No validation library needed for internal results. | HIGH |

**Why django-health-check:**
- Official Django health check library with 2.7k GitHub stars
- Pluggable backend system - extend `BaseHealthCheckBackend` for each integration
- Built-in checks for database, cache, storage
- `/ht/` endpoint returns HTTP 200 (healthy) or 500 (unhealthy)
- JSON and HTML response formats
- Integrates with monitoring tools (Prometheus, Datadog, New Relic)

**Why NOT Pydantic for health check results:**
- Health check results are internal (not API boundaries)
- No runtime validation needed - health checks are trusted internal code
- Adds 8+ dependencies unnecessarily
- Frozen dataclasses are faster and sufficient

**Why synchronous health checks (not async):**
- Health checks are simple I/O operations (API calls, DB queries)
- No concurrent operations to benefit from async
- Django transactions don't work in async mode (need atomic result updates)
- Async adds ~1ms context-switch overhead without benefit
- Most health checks complete in <100ms

**Connection testing pattern:**
```python
# Use requests with retry strategy
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=1,  # 1s, 2s, 4s
)
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

# Timeout tuple: (connect_timeout, read_timeout)
# 3.05s = slightly > TCP retransmission window (3s)
response = session.post(url, json=payload, timeout=(3.05, 27))
```

**GraphQL health check pattern (Linear API):**
```python
# Use introspection query - all GraphQL servers support __typename
query = """
query HealthCheck {
    __typename
}
"""
response = session.post(
    "https://api.linear.app/graphql",
    json={"query": query},
    headers={"Authorization": api_key},
    timeout=(3.05, 27),
)
```

**Health check result dataclass:**
```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class HealthCheckResult:
    """Immutable health check result."""
    status: Literal["healthy", "degraded", "error"]
    message: str
    response_time_ms: float | None = None
    details: dict | None = None
```

**Custom health check backend:**
```python
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import HealthCheckException

class LinearHealthCheckBackend(BaseHealthCheckBackend):
    critical_service = True  # HTTP 500 if this fails

    def check_status(self):
        result = test_linear_connection(...)
        if result.status != "healthy":
            self.add_error(HealthCheckException(result.message))

    def identifier(self):
        return "Linear API"
```

**Sources:**
- [django-health-check 3.20.8 (PyPI)](https://pypi.org/project/django-health-check/)
- [django-health-check docs](https://django-health-check.readthedocs.io/en/latest/)
- [requests 2.32.5 (PyPI)](https://pypi.org/project/requests/)
- [Python Requests Timeout Best Practices](https://oxylabs.io/blog/python-requests-timeout)
- [Python Requests Retry Best Practices](https://www.zenrows.com/blog/python-requests-retry)
- [Frozen Dataclasses Best Practices](https://testdriven.io/tips/671b59e7-ba72-4201-82d4-473c8e594c55/)
- [Django Async Support (When NOT to use async)](https://docs.djangoproject.com/en/6.0/topics/async/)
- [Linear GraphQL API](https://linear.app/developers/graphql)
- [Apollo GraphQL Health Checks](https://www.apollographql.com/docs/apollo-server/monitoring/health-checks)

---

### Background Tasks (Optional)

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **Huey** | 2.x | Task queue | Lightweight, Redis-backed, 60MB memory, simple setup | MEDIUM |
| **Django-Q2** | (alternative) | Task queue | Can use database (no Redis), if avoiding external services | MEDIUM |

**When needed:**
- CI webhook processing (if async)
- Periodic test result aggregation
- Large codebase spec parsing

**When NOT needed (start without):**
- Sync webhook handlers are fine for low-medium traffic
- Spec parsing can be on-demand
- Add when you have proven need

**Recommendation:** Start without background tasks. Add Huey when sync processing becomes a bottleneck.

**Source:** [Lightweight Django Task Queues 2025](https://medium.com/@g.suryawanshi/lightweight-django-task-queues-in-2025-beyond-celery-74a95e0548ec)

---

### API Layer (If Needed)

| Technology | Version | Purpose | Rationale | Confidence |
|------------|---------|---------|-----------|------------|
| **Django views** | (built-in) | Internal API | Standard Django views for HTMX endpoints, no framework needed | HIGH |
| **Django REST Framework** | 3.15.x | External API | If external integrations needed (CI systems, other tools) | MEDIUM |

**Why not start with DRF:**
- Dashboard uses HTMX (returns HTML fragments, not JSON)
- Test results can be pushed via simple POST endpoint
- DRF adds complexity for internal tools

**When to add DRF:**
- Third-party integrations need JSON API
- Mobile app or external dashboard
- Programmatic access from other tools

**Source:** [DRF vs Django Ninja comparison](https://www.loopwerk.io/articles/2024/drf-vs-ninja/)

---

## Complete Installation

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Core framework
pip install Django==5.2.9

# Database (choose one)
pip install psycopg[binary]  # PostgreSQL
# or use SQLite (built-in)

# Admin dashboard
pip install django-unfold==0.76.0
pip install django-htmx==1.27.0

# Tree structure
pip install django-treebeard==4.8.0

# Spec parsing
pip install python-frontmatter==1.1.0
pip install Markdown==3.10

# Testing
pip install pytest==9.0.2
pip install pytest-django==4.11.1
pip install pytest-json-report==1.5.0

# Integration health checks (NEW)
pip install django-health-check==3.20.8
pip install requests==2.32.5  # Already installed for Linear client

# Optional: Background tasks
# pip install huey==2.5.0
# pip install redis==5.0.0
```

### requirements.txt / pyproject.toml

```toml
dependencies = [
    "Django>=5.2,<5.3",
    "psycopg[binary]>=3.1",
    "django-unfold>=0.76,<1.0",
    "django-htmx>=1.27,<2.0",
    "django-treebeard>=4.8,<5.0",
    "python-frontmatter>=1.1,<2.0",
    "Markdown>=3.10,<4.0",
    "pytest>=9.0,<10.0",
    "pytest-django>=4.11,<5.0",
    "pytest-json-report>=1.5,<2.0",
    "django-health-check>=3.20.8,<4.0",  # NEW
    "requests>=2.32,<3.0",  # NEW (for health checks + Linear client)
]
```

### INSTALLED_APPS additions for health checks

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'health_check',  # NEW
    'health_check.db',  # NEW - database health check
    'health_check.cache',  # NEW - cache health check (if using cache)
]
```

---

## What NOT to Use

| Technology | Why Avoid |
|------------|-----------|
| **django-mptt** | Officially unmaintained. Use django-treebeard instead. |
| **Celery** | Overkill for this use case. 150MB memory, complex setup with RabbitMQ/Redis. Huey or Django-Q2 are simpler. |
| **React/Vue SPA** | Violates single-repo Python requirement, adds build complexity. HTMX provides sufficient interactivity. |
| **FastAPI** | Would require separate service. Django's admin + ORM are the value here. |
| **Django Ninja** | Less mature, smaller community, worse error handling than DRF. If you need API, use DRF. |
| **Custom admin from scratch** | Months of work. Unfold + django.contrib.admin is 90% there. |
| **MongoDB / NoSQL** | Hierarchical data is well-served by PostgreSQL. JSONB handles flexible metadata. |
| **Pydantic** (for health checks) | Unnecessary for internal health check results. Use frozen dataclasses. |
| **httpx / aiohttp** (for health checks) | Async not beneficial for simple health checks. Use requests with retry strategy. |
| **gql / graphene-python** | GraphQL is just JSON POST with requests. No library needed. |
| **APScheduler / django-cron** | Use management commands + system cron if periodic health checks needed. |

---

## Architecture Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Django 5.2 LTS | Mature, admin-ready, single repo |
| Database | PostgreSQL 14+ | Concurrent writes, JSONB, full-text search |
| Dashboard | django-unfold + HTMX | Modern UX without SPA complexity |
| Tree storage | django-treebeard (materialized path) | Balanced read/write, actively maintained |
| Test linking | pytest markers | Idiomatic, validated at collection time |
| Spec format | YAML frontmatter + Markdown | Human-readable, git-friendly |
| Background tasks | None initially (Huey when needed) | YAGNI - add complexity when proven need |
| Health checks | django-health-check + requests | Pluggable backends, minimal dependencies |
| Health check results | Frozen dataclasses | Immutable, fast, no validation overhead |
| Health check execution | Synchronous | Simple I/O operations, no async benefit |

---

## Version Verification Sources

All versions verified from official sources on 2026-01-19 (health check additions verified 2026-01-21):

| Package | Version | Source |
|---------|---------|--------|
| Django | 5.2.9 | [Django releases](https://docs.djangoproject.com/en/5.1/releases/) |
| pytest | 9.0.2 | [PyPI](https://pypi.org/project/pytest/) |
| pytest-django | 4.11.1 | [pytest-django changelog](https://pytest-django.readthedocs.io/en/latest/changelog.html) |
| django-unfold | 0.76.0 | [PyPI](https://pypi.org/project/django-unfold/) |
| django-htmx | 1.27.0 | [PyPI](https://pypi.org/project/django-htmx/) |
| django-treebeard | 4.8.0 | [PyPI](https://pypi.org/project/django-treebeard/) |
| python-frontmatter | 1.1.0 | [PyPI](https://pypi.org/project/python-frontmatter/) |
| Python-Markdown | 3.10 | [PyPI](https://pypi.org/project/Markdown/) |
| pytest-json-report | 1.5.0 | [PyPI](https://pypi.org/project/pytest-json-report/) |
| **django-health-check** | **3.20.8** | **[PyPI](https://pypi.org/project/django-health-check/)** (Dec 2025) |
| **requests** | **2.32.5** | **[PyPI](https://pypi.org/project/requests/)** (Aug 2025) |
