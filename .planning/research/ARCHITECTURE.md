# Architecture Patterns: SpecTrace

**Domain:** Requirements Traceability System (Spec-to-Test)
**Researched:** 2026-01-19
**Confidence:** HIGH

## Recommended Architecture

SpecTrace follows a **pipeline architecture** with distinct processing stages feeding into a central data store, surfaced through a web dashboard. This pattern is standard for traceability systems that aggregate data from multiple sources (specs, tests, CI).

```
                                    +------------------+
                                    |   Django Web     |
                                    |   Dashboard      |
                                    |   (Read-Only)    |
                                    +--------+---------+
                                             |
                                             | reads
                                             v
+----------------+    +-----------------+    +------------------+
| Spec Parser    |--->|                 |<---| CI Results       |
| (Markdown)     |    |  PostgreSQL DB  |    | Aggregator       |
+----------------+    |  (Central Store)|    +------------------+
                      |                 |           ^
+----------------+    +-----------------+           |
| Test Collector |----------^                      |
| (Pytest Plugin)|                          webhooks/polling
+----------------+                                 |
                                            +------+------+
                                            | CI Systems  |
                                            | (GitHub/GL) |
                                            +-------------+
```

### Data Flow Summary

1. **Spec Parsing:** Markdown files in `specs/` are parsed to extract requirement IDs and metadata
2. **Test Collection:** Pytest collects tests and extracts `@pytest.mark.requirement()` markers
3. **CI Integration:** Test results from CI runs are aggregated and linked to requirement IDs
4. **Dashboard:** Surfaces the traceability matrix showing requirement -> test -> result status

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **Spec Parser** | Parse markdown specs into structured requirements | `.md` files in `specs/` | Requirement records in DB | PostgreSQL (write) |
| **Test Collector** | Extract requirement markers from tests | Python test files | Test-to-requirement mappings in DB | PostgreSQL (write), Pytest hooks |
| **CI Aggregator** | Ingest test results from CI systems | Webhooks, JUnit XML | Test result records in DB | PostgreSQL (write), CI APIs |
| **Traceability Engine** | Compute coverage status per requirement | DB queries | Coverage status, gap analysis | PostgreSQL (read) |
| **Django Dashboard** | Display traceability matrix to PMs | User requests | HTML views, JSON API | PostgreSQL (read), Traceability Engine |
| **CLI Tool** | Developer interface for local operations | Command line | Console output, DB writes | All components |

### Component Details

#### 1. Spec Parser

**Purpose:** Convert hierarchical markdown specs into database records.

**Key Design Decisions:**
- Use [mistletoe](https://github.com/miyuchina/mistletoe) for CommonMark-compliant AST parsing
- Extract requirement IDs from heading structure (e.g., `# Feature / ## REQ-001: Requirement Name`)
- Support frontmatter YAML for requirement metadata (status, priority, owner)
- Watch for file changes to trigger re-parsing (inotify or polling)

**Input Format Example:**
```markdown
---
feature: user-authentication
status: draft
---

# User Authentication

## REQ-AUTH-001: Login with Email

Users must be able to log in with email and password.

### Acceptance Criteria
- AC1: Valid credentials grant access
- AC2: Invalid credentials show error message
```

**Output:** Requirement records with ID, title, description, hierarchy path, metadata.

#### 2. Test Collector (Pytest Plugin)

**Purpose:** Extract requirement linkages from pytest test markers.

**Key Design Decisions:**
- Implement as pytest plugin using `pytest_collection_finish` hook
- Custom marker: `@pytest.mark.requirement("REQ-AUTH-001")`
- Support multiple requirements per test: `@pytest.mark.requirement("REQ-001", "REQ-002")`
- Register marker in `pytest.ini` to avoid warnings
- Store mappings: test_id (file::class::function) -> requirement_ids

**Implementation Pattern:**
```python
# conftest.py (or pytest plugin)
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requirement(id): Link test to requirement ID(s)"
    )

def pytest_collection_finish(session):
    """Extract requirement markers after collection."""
    mappings = []
    for item in session.items:
        req_markers = list(item.iter_markers(name="requirement"))
        for marker in req_markers:
            for req_id in marker.args:
                mappings.append({
                    "test_id": item.nodeid,
                    "requirement_id": req_id,
                    "test_file": str(item.fspath),
                    "test_name": item.name
                })
    # Write to DB or export as JSON
```

**Sources:**
- [pytest markers documentation](https://docs.pytest.org/en/stable/how-to/mark.html)
- [pytest hooks documentation](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html)

#### 3. CI Results Aggregator

**Purpose:** Ingest test results from CI systems and link to requirements.

**Key Design Decisions:**
- **Primary:** Webhook-based for real-time updates (CI posts to SpecTrace)
- **Fallback:** Polling as backup for missed webhooks (learned from [Harness CI architecture](https://www.harness.io/blog/architecting-harness-ci-for-scale))
- Parse JUnit XML format (standard CI output)
- Use [junitparser](https://pypi.org/project/junitparser/) library for XML parsing
- Idempotent processing: track event IDs to handle duplicate webhooks

**Data Flow:**
```
CI Run Completes
      |
      v
+-----+-----+
| Webhook   |  (POST /api/ci/results/)
+-----------+
      |
      v
Parse JUnit XML
      |
      v
Match test_id to existing test-requirement mappings
      |
      v
Create TestResult records (passed/failed/skipped, timestamp, CI run ID)
      |
      v
Update Requirement.verification_status (computed)
```

**Webhook Payload Structure:**
```json
{
  "event_id": "unique-event-id",
  "ci_system": "github-actions",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "junit_xml_url": "https://...",  // or inline
  "junit_xml": "<testsuite>...</testsuite>"
}
```

#### 4. Traceability Engine

**Purpose:** Compute coverage metrics and gap analysis.

**Key Design Decisions:**
- Query-based computation (not materialized) for simplicity initially
- Support forward traceability (requirement -> tests -> results)
- Support backward traceability (test -> requirements)
- Compute coverage percentages and identify gaps

**Core Queries:**
- Requirements without linked tests (coverage gaps)
- Tests without passing results (verification failures)
- Requirements fully verified (all linked tests passing)
- Orphaned tests (tests not linked to any requirement)

**Coverage Status States:**
| Status | Definition |
|--------|------------|
| `NOT_COVERED` | No tests linked to requirement |
| `PARTIALLY_COVERED` | Some tests linked, but not all passing |
| `VERIFIED` | At least one test linked and all linked tests passing |
| `FAILING` | Tests linked but latest results show failures |

#### 5. Django Dashboard

**Purpose:** Web interface for PMs to view traceability status.

**Key Design Decisions:**
- Read-only dashboard (no write operations through UI initially)
- Server-side rendering for simplicity (Django templates + HTMX for interactivity)
- Optional: Django Channels for real-time updates when CI results arrive
- Filter by: feature, status, date range, verification state

**Key Views:**
| View | Purpose | URL Pattern |
|------|---------|-------------|
| Traceability Matrix | Grid showing requirements vs tests | `/matrix/` |
| Requirement Detail | Single requirement with linked tests and history | `/requirements/<id>/` |
| Coverage Dashboard | High-level metrics and charts | `/dashboard/` |
| Gap Analysis | Requirements missing test coverage | `/gaps/` |
| Test Results Timeline | Recent CI results chronologically | `/results/` |

**Sources:**
- [Building dashboards with Django and D3](https://dreisbach.us/articles/building-dashboards-with-django-and-d3/)
- [Real-time data processing in Django](https://medium.com/@sachinlokesh97/real-time-data-processing-in-django-building-a-live-dashboard-with-django-channels-and-celery-25281bc128d6)

#### 6. CLI Tool

**Purpose:** Developer interface for local operations.

**Commands:**
```bash
spectrace parse          # Parse all specs, update DB
spectrace collect        # Run pytest collection, extract markers, update DB
spectrace status         # Show coverage summary
spectrace status REQ-001 # Show specific requirement status
spectrace sync           # Full sync: parse + collect + fetch latest CI results
spectrace serve          # Start Django dashboard locally
```

## Database Schema

**Design Principle:** Normalize for flexibility, denormalize computed fields for query performance.

### Core Models

```
+------------------+       +-------------------+       +------------------+
|   Requirement    |       | TestRequirement   |       |      Test        |
+------------------+       +-------------------+       +------------------+
| id (PK)          |<----->| requirement_id FK |<----->| id (PK)          |
| external_id      |       | test_id FK        |       | node_id (unique) |
| title            |       | created_at        |       | file_path        |
| description      |       +-------------------+       | function_name    |
| hierarchy_path   |                                   | class_name       |
| feature          |                                   | last_collected   |
| status           |                                   +------------------+
| priority         |                                           |
| metadata (JSON)  |                                           |
| created_at       |                                           v
| updated_at       |                                   +------------------+
+------------------+                                   |   TestResult     |
        |                                              +------------------+
        |                                              | id (PK)          |
        v                                              | test_id FK       |
+------------------+                                   | ci_run_id FK     |
|     Feature      |                                   | status (enum)    |
+------------------+                                   | duration_ms      |
| id (PK)          |                                   | error_message    |
| name (unique)    |                                   | created_at       |
| path             |                                   +------------------+
| parent_id FK     |                                           |
+------------------+                                           v
                                                       +------------------+
                                                       |     CIRun        |
                                                       +------------------+
                                                       | id (PK)          |
                                                       | event_id (unique)|
                                                       | ci_system        |
                                                       | repository       |
                                                       | branch           |
                                                       | commit_sha       |
                                                       | started_at       |
                                                       | completed_at     |
                                                       +------------------+
```

### Relationships

| Relationship | Type | Notes |
|--------------|------|-------|
| Requirement <-> Test | Many-to-Many | Via `TestRequirement` junction table |
| Test -> TestResult | One-to-Many | One test has many results over time |
| TestResult -> CIRun | Many-to-One | Each result belongs to one CI run |
| Requirement -> Feature | Many-to-One | Requirements grouped by feature |
| Feature -> Feature | Self-referential | Hierarchical feature tree |

### Computed/Cached Fields

Consider adding these as cached fields updated on write:

```python
class Requirement(models.Model):
    # ... core fields ...

    # Cached computed fields (updated by signals/triggers)
    test_count = models.IntegerField(default=0)
    passing_test_count = models.IntegerField(default=0)
    verification_status = models.CharField(max_length=20)  # computed
    last_verified_at = models.DateTimeField(null=True)
```

**Sources:**
- [Requirements Traceability Matrix](https://www.softwaretestinghelp.com/requirements-traceability-matrix/)
- [Django many-to-many relationships](https://codesignal.com/learn/courses/advanced-database-schema-design-in-django/lessons/many-to-many-relationship-basics)

## Patterns to Follow

### Pattern 1: Event Sourcing for CI Results

**What:** Store all CI results as immutable events, compute current status from history.

**When:** You need audit trails and historical analysis of verification status.

**Why:** Traceability systems need to answer "when was this requirement last verified?" and "what broke between CI runs?"

**Example:**
```python
class TestResult(models.Model):
    """Immutable record of a single test execution."""
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='results')
    ci_run = models.ForeignKey(CIRun, on_delete=models.CASCADE)
    status = models.CharField(choices=[('passed', 'Passed'), ('failed', 'Failed'), ('skipped', 'Skipped')])
    # Never update, only create new records

    class Meta:
        # Allow only one result per test per CI run
        unique_together = ['test', 'ci_run']
```

### Pattern 2: Idempotent Webhook Processing

**What:** Use unique event IDs to ensure webhooks are processed exactly once.

**When:** Always, for any webhook-based ingestion.

**Why:** Network issues and retries can deliver the same webhook multiple times.

**Example:**
```python
@transaction.atomic
def process_ci_webhook(payload):
    event_id = payload['event_id']

    # Idempotency check
    if CIRun.objects.filter(event_id=event_id).exists():
        return {"status": "already_processed"}

    # Process webhook...
    ci_run = CIRun.objects.create(event_id=event_id, ...)
    # ...
```

**Source:** [ByteByteGo: Polling vs Webhooks](https://blog.bytebytego.com/p/ep100-polling-vs-webhooks)

### Pattern 3: Hierarchical Requirement IDs

**What:** Use structured IDs that encode hierarchy (e.g., `REQ-AUTH-001`).

**When:** Requirements have natural feature groupings.

**Why:** Enables filtering, grouping, and navigation without additional metadata.

**Convention:**
```
REQ-{FEATURE}-{NUMBER}

Examples:
REQ-AUTH-001   (Authentication feature, requirement 1)
REQ-AUTH-002   (Authentication feature, requirement 2)
REQ-PAY-001    (Payments feature, requirement 1)
```

### Pattern 4: Separate Collection from Execution

**What:** Test collection (discovering tests and markers) is separate from test execution (running tests).

**When:** You need requirement mappings without running tests.

**Why:** Collection is fast and safe; execution is slow and has side effects.

**Implementation:**
```bash
# Collection only (no test execution)
pytest --collect-only -q

# In pytest plugin, use pytest_collection_finish hook
# NOT pytest_runtest_* hooks
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Computed Status Only

**What:** Storing only the current verification status without the underlying results.

**Why bad:** Loses audit trail, can't debug why status changed, can't recover from bugs.

**Instead:** Store all test results as events, compute status on read or cache with triggers.

### Anti-Pattern 2: Inline Test-to-Requirement Mapping

**What:** Storing requirement IDs directly in test files as comments parsed at runtime.

**Why bad:** Comments are fragile, not type-checked, easily broken by refactoring.

**Instead:** Use pytest markers which are:
- Explicitly registered
- Type-checkable with mypy
- Accessible via pytest's API
- Won't break if test code is refactored

```python
# BAD: Comment-based
def test_login():
    # requirement: REQ-AUTH-001
    ...

# GOOD: Marker-based
@pytest.mark.requirement("REQ-AUTH-001")
def test_login():
    ...
```

### Anti-Pattern 3: Synchronous CI Result Processing

**What:** Processing CI webhooks synchronously in the web request.

**Why bad:** Large test suites = large JUnit XML = slow parsing = webhook timeout.

**Instead:** Accept webhook immediately, queue processing via Celery.

```python
# BAD: Synchronous
@api_view(['POST'])
def ci_webhook(request):
    parse_junit_xml(request.data['junit_xml'])  # Slow!
    return Response({'status': 'ok'})

# GOOD: Async with Celery
@api_view(['POST'])
def ci_webhook(request):
    process_ci_results.delay(request.data)  # Queue it
    return Response({'status': 'accepted'})
```

### Anti-Pattern 4: Bidirectional Coupling Between Parser and Dashboard

**What:** Spec parser imports Django models directly.

**Why bad:** Can't run parser outside Django context, testing is harder, circular dependencies.

**Instead:** Parser writes to DB via well-defined interface (repository pattern) or produces JSON that a separate importer consumes.

## Suggested Build Order

Based on component dependencies, build in this order:

```
Phase 1: Foundation
+------------------+
|  Database Schema |  (Django models)
+------------------+
|  Spec Parser     |  (Can work standalone)
+------------------+

Phase 2: Test Integration
+------------------+
|  Test Collector  |  (Pytest plugin)
+------------------+
|  CLI Tool        |  (parse + collect commands)
+------------------+

Phase 3: Dashboard
+------------------+
|  Traceability    |  (Query logic)
|  Engine          |
+------------------+
|  Django Views    |  (Read-only dashboard)
+------------------+

Phase 4: CI Integration
+------------------+
|  CI Aggregator   |  (Webhooks + polling)
+------------------+
|  Real-time       |  (Django Channels, optional)
+------------------+
```

### Build Order Rationale

1. **Database Schema First:** Everything depends on the data model. Get this right early.

2. **Spec Parser Before Tests:** Requirements must exist before tests can link to them. Parser is also simpler (fewer dependencies).

3. **Test Collector Before Dashboard:** Need test-requirement mappings to show anything meaningful on dashboard.

4. **Dashboard Before CI:** You can demo the system with manual "test ran and passed" entries before CI automation.

5. **CI Integration Last:** Most complex (webhooks, external systems, async processing). Also most optional for MVP.

### MVP Scope

For a working MVP, you need:
- Database schema (all core models)
- Spec parser (basic markdown -> requirements)
- Test collector (pytest plugin with marker extraction)
- CLI (parse + collect + status commands)
- Dashboard (read-only traceability matrix)

Defer to post-MVP:
- CI integration (can manually import results initially)
- Real-time updates (polling/refresh is fine for MVP)
- Advanced features (gap analysis views, historical trends)

## Scalability Considerations

| Concern | At 100 requirements | At 10K requirements | At 100K requirements |
|---------|---------------------|---------------------|----------------------|
| **Spec Parsing** | In-memory, instant | Incremental (changed files only) | Parallel parsing, file watching |
| **Test Collection** | < 1 second | 5-10 seconds | Consider caching collection results |
| **Dashboard Queries** | No optimization needed | Add indexes, pagination | Materialized views, search index |
| **CI Result Storage** | Single table | Partition by date | Archive old results, summary tables |
| **Traceability Matrix** | Render full grid | Virtual scrolling, lazy load | Pre-computed summaries, drill-down |

### Performance Notes

- **Postgres is sufficient** for most SpecTrace deployments (even at 100K requirements)
- **Indexes needed:** `Requirement.external_id`, `Test.node_id`, `CIRun.event_id`, `TestResult(test_id, ci_run_id)`
- **Consider:** Full-text search on requirement descriptions (Postgres built-in or Elasticsearch for large deployments)

## Sources

**Official Documentation:**
- [pytest markers documentation](https://docs.pytest.org/en/stable/how-to/mark.html)
- [pytest hooks documentation](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html)
- [pytest API reference](https://docs.pytest.org/en/stable/reference/reference.html)
- [junitparser documentation](https://junitparser.readthedocs.io/)
- [mistletoe markdown parser](https://github.com/miyuchina/mistletoe)

**Architecture Patterns:**
- [ByteByteGo: Polling vs Webhooks](https://blog.bytebytego.com/p/ep100-polling-vs-webhooks)
- [Harness CI Architecture](https://www.harness.io/blog/architecting-harness-ci-for-scale)
- [Building dashboards with Django and D3](https://dreisbach.us/articles/building-dashboards-with-django-and-d3/)
- [Real-time data processing in Django](https://medium.com/@sachinlokesh97/real-time-data-processing-in-django-building-a-live-dashboard-with-django-channels-and-celery-25281bc128d6)

**Traceability Concepts:**
- [Requirements Traceability - Wikipedia](https://en.wikipedia.org/wiki/Requirements_traceability)
- [Requirements Traceability Matrix](https://www.softwaretestinghelp.com/requirements-traceability-matrix/)
- [Traceability Matrix Types](https://aqua-cloud.io/traceability-matrix/)
- [GeeksforGeeks RTM Guide](https://www.geeksforgeeks.org/software-testing/requirement-traceability-matrix/)
