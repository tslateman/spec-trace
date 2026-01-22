# Architecture Patterns: Integration Health Checks

**Domain:** Requirements Traceability System - Integration Health Monitoring
**Research Focus:** Health check architecture for existing SpecTrace milestone
**Researched:** 2026-01-21
**Confidence:** HIGH

## Executive Summary

Integration health checks extend the existing SpecTrace architecture with a verification layer that tests external integration health (Linear API, SLO platforms, etc.). The recommended pattern uses dataclass-based domain objects for check results with Django model persistence for historical tracking, following the Repository pattern to separate health check logic from persistence.

The existing architecture already demonstrates this separation pattern with `status.py` containing computation logic and `models.py` containing persistence, making health checks a natural extension.

## Existing Architecture Analysis

### Current Component Structure

| Component | Responsibility | Location |
|-----------|---------------|----------|
| Models Layer | Data persistence, ORM definitions | `requirements/models.py` |
| Status Computation | Verification logic, aggregation rules | `requirements/status.py` |
| API Layer | External push endpoints for status updates | `requirements/api.py` |
| Admin Layer | Django-unfold display, status badges | `requirements/admin.py` |
| Dashboard | Metrics aggregation for admin index | `requirements/dashboard.py` |
| Integration Client | LinearClient for external API | `requirements/linear.py` |

### Key Architecture Patterns Already in Use

**1. Separation of Computation from Persistence**
- `status.py` computes verification status without touching the API
- `api.py` handles external updates and triggers recomputation
- Models store the computed results

**2. Multi-Check Aggregation**
- `compute_unified_verification_status()` aggregates test + inapp + SLO
- Verification method determines aggregation logic (TEST, INAPP, BOTH, UNSPECIFIED)
- Worst-case-wins for failures (any breach = failing)

**3. Django-Unfold Dashboard Integration**
- `dashboard_callback()` provides metrics via context injection
- No separate views needed, pure data computation
- Template rendering handled by unfold

**4. REST API Pattern**
- POST endpoints for external systems to push updates
- GET endpoints for status queries
- JSON responses with structured error handling

## Integration Health Check Architecture

### Recommended Pattern: Domain Objects + Repository

Following Architecture Patterns with Python (Cosmic Python) and current Django best practices, use dataclasses for domain objects with Django models for persistence.

#### Why This Pattern

**Separation of Concerns:**
- Health check logic independent of Django ORM
- Easy to test without database
- Can execute checks without persisting results

**Consistency with Existing Code:**
- `status.py` already separates computation from persistence
- `LinearClient` already demonstrates external integration pattern
- Natural extension of existing architecture

**Framework Independence:**
- Health check classes don't depend on Django
- Could reuse in CLI tools, background jobs, or different frameworks
- Domain logic stays pure Python

### Component Design

#### 1. Domain Objects (New: `requirements/health_checks/domain.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class CheckStatus(Enum):
    """Status of a health check execution."""
    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass
class VerificationCheck:
    """Result of a single health check execution.

    Pure domain object, no Django dependencies.
    """
    check_name: str
    status: CheckStatus
    message: str
    checked_at: datetime
    details: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        """Check passed without failures."""
        return self.status in (CheckStatus.SUCCESS, CheckStatus.WARNING)

    @property
    def is_critical_failure(self) -> bool:
        """Check failed critically."""
        return self.status == CheckStatus.FAILURE


@dataclass
class TestConnectionResult:
    """Result of testing an integration connection.

    Aggregates multiple verification checks.
    """
    integration_name: str
    overall_status: CheckStatus
    checks: list[VerificationCheck]
    tested_at: datetime

    @property
    def is_healthy(self) -> bool:
        """All checks passed."""
        return all(check.is_healthy for check in self.checks)

    @property
    def critical_failures(self) -> list[VerificationCheck]:
        """Checks that failed critically."""
        return [c for c in self.checks if c.is_critical_failure]
```

#### 2. Health Checker Classes (New: `requirements/health_checks/checkers.py`)

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

from .domain import CheckStatus, TestConnectionResult, VerificationCheck


class HealthChecker(ABC):
    """Base class for integration health checkers."""

    @property
    @abstractmethod
    def integration_name(self) -> str:
        """Name of the integration being checked."""
        pass

    @abstractmethod
    def test_connection(self) -> TestConnectionResult:
        """Execute all health checks for this integration."""
        pass


class LinearHealthChecker(HealthChecker):
    """Health checker for Linear API integration."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = LinearClient(api_key)

    @property
    def integration_name(self) -> str:
        return "Linear"

    def test_connection(self) -> TestConnectionResult:
        """Test Linear API connection and permissions."""
        checks = [
            self._check_authentication(),
            self._check_api_reachability(),
            self._check_query_permissions(),
        ]

        # Aggregate status: worst case wins
        if any(c.status == CheckStatus.FAILURE for c in checks):
            overall = CheckStatus.FAILURE
        elif any(c.status == CheckStatus.WARNING for c in checks):
            overall = CheckStatus.WARNING
        elif any(c.status == CheckStatus.UNKNOWN for c in checks):
            overall = CheckStatus.UNKNOWN
        else:
            overall = CheckStatus.SUCCESS

        return TestConnectionResult(
            integration_name=self.integration_name,
            overall_status=overall,
            checks=checks,
            tested_at=datetime.now(),
        )

    def _check_authentication(self) -> VerificationCheck:
        """Verify API key is valid."""
        try:
            # Simple viewer query to test auth
            query = "query { viewer { id name } }"
            result = self.client._execute_query(query)

            if 'viewer' in result and result['viewer']:
                return VerificationCheck(
                    check_name="authentication",
                    status=CheckStatus.SUCCESS,
                    message=f"Authenticated as {result['viewer']['name']}",
                    checked_at=datetime.now(),
                    details={"viewer_id": result['viewer']['id']},
                )
            else:
                return VerificationCheck(
                    check_name="authentication",
                    status=CheckStatus.FAILURE,
                    message="Authentication failed: Invalid response",
                    checked_at=datetime.now(),
                )
        except Exception as e:
            return VerificationCheck(
                check_name="authentication",
                status=CheckStatus.FAILURE,
                message="Authentication failed",
                checked_at=datetime.now(),
                error=str(e),
            )

    def _check_api_reachability(self) -> VerificationCheck:
        """Verify Linear API endpoint is reachable."""
        # Implementation similar to above
        ...

    def _check_query_permissions(self) -> VerificationCheck:
        """Verify API key has required query permissions."""
        # Implementation similar to above
        ...


class SLOHealthChecker(HealthChecker):
    """Health checker for SLO platform integration."""

    @property
    def integration_name(self) -> str:
        return "SLO Platform"

    def test_connection(self) -> TestConnectionResult:
        """Test SLO platform connectivity."""
        # Implementation depends on SLO platform (Datadog, New Relic, etc.)
        ...
```

#### 3. Persistence Layer (New: `requirements/models.py` additions)

```python
class IntegrationHealth(models.Model):
    """Historical record of integration health check results."""

    integration_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Name of integration (Linear, SLO Platform, etc.)"
    )
    overall_status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('failure', 'Failure'),
            ('unknown', 'Unknown'),
        ],
        help_text="Overall health status"
    )
    checked_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When health check was performed"
    )

    class Meta:
        ordering = ['-checked_at']
        verbose_name = "Integration Health Check"
        verbose_name_plural = "Integration Health Checks"


class IntegrationHealthCheck(models.Model):
    """Individual check result within a health check run."""

    health_run = models.ForeignKey(
        IntegrationHealth,
        on_delete=models.CASCADE,
        related_name='checks'
    )
    check_name = models.CharField(
        max_length=100,
        help_text="Name of specific check (authentication, reachability, etc.)"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('failure', 'Failure'),
            ('unknown', 'Unknown'),
        ],
    )
    message = models.TextField(
        help_text="Check result message"
    )
    error = models.TextField(
        blank=True,
        help_text="Error details if check failed"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional check details"
    )

    class Meta:
        ordering = ['check_name']
```

#### 4. Repository Pattern (New: `requirements/health_checks/repository.py`)

```python
from requirements.models import IntegrationHealth, IntegrationHealthCheck
from .domain import TestConnectionResult


class HealthCheckRepository:
    """Repository for persisting health check results."""

    @staticmethod
    def save_result(result: TestConnectionResult) -> IntegrationHealth:
        """Persist a TestConnectionResult to database.

        Args:
            result: Domain object containing health check results

        Returns:
            Created IntegrationHealth model instance
        """
        health_run = IntegrationHealth.objects.create(
            integration_name=result.integration_name,
            overall_status=result.overall_status.value,
            checked_at=result.tested_at,
        )

        for check in result.checks:
            IntegrationHealthCheck.objects.create(
                health_run=health_run,
                check_name=check.check_name,
                status=check.status.value,
                message=check.message,
                error=check.error or '',
                details=check.details,
            )

        return health_run

    @staticmethod
    def get_latest_result(integration_name: str) -> IntegrationHealth | None:
        """Get most recent health check for an integration."""
        return IntegrationHealth.objects.filter(
            integration_name=integration_name
        ).first()

    @staticmethod
    def get_health_history(integration_name: str, limit: int = 10):
        """Get recent health check history."""
        return IntegrationHealth.objects.filter(
            integration_name=integration_name
        ).prefetch_related('checks')[:limit]
```

#### 5. API Endpoints (Extend: `requirements/api.py`)

```python
from requirements.health_checks.checkers import LinearHealthChecker, SLOHealthChecker
from requirements.health_checks.repository import HealthCheckRepository


@require_http_methods(["POST"])
def test_linear_connection(request):
    """Test Linear integration health.

    POST /api/integrations/linear/test/

    Request body:
    {
        "api_key": "lin_api_xxx"
    }

    Response:
    {
        "success": true,
        "integration": "Linear",
        "overall_status": "success",
        "checks": [
            {
                "name": "authentication",
                "status": "success",
                "message": "Authenticated as User Name"
            },
            ...
        ],
        "tested_at": "2026-01-21T10:30:00Z"
    }
    """
    try:
        data = json.loads(request.body)
        api_key = data.get('api_key')

        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'api_key required'
            }, status=400)

        # Execute health checks
        checker = LinearHealthChecker(api_key)
        result = checker.test_connection()

        # Optionally persist results
        if data.get('save_result', False):
            HealthCheckRepository.save_result(result)

        return JsonResponse({
            'success': True,
            'integration': result.integration_name,
            'overall_status': result.overall_status.value,
            'checks': [
                {
                    'name': check.check_name,
                    'status': check.status.value,
                    'message': check.message,
                    'error': check.error,
                    'details': check.details,
                }
                for check in result.checks
            ],
            'tested_at': result.tested_at.isoformat(),
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_integration_health(request, integration_name):
    """Get latest health status for an integration.

    GET /api/integrations/{integration_name}/health/

    Response:
    {
        "integration": "Linear",
        "latest_status": "success",
        "last_checked": "2026-01-21T10:30:00Z",
        "checks": [...]
    }
    """
    latest = HealthCheckRepository.get_latest_result(integration_name)

    if not latest:
        return JsonResponse({
            'integration': integration_name,
            'latest_status': 'unknown',
            'message': 'No health checks recorded'
        })

    return JsonResponse({
        'integration': integration_name,
        'latest_status': latest.overall_status,
        'last_checked': latest.checked_at.isoformat(),
        'checks': [
            {
                'name': check.check_name,
                'status': check.status,
                'message': check.message,
            }
            for check in latest.checks.all()
        ]
    })
```

#### 6. Dashboard Integration (Extend: `requirements/dashboard.py`)

```python
from requirements.health_checks.repository import HealthCheckRepository


def dashboard_callback(request, context):
    """Extend existing dashboard with integration health metrics."""

    # ... existing metrics code ...

    # Integration health status
    linear_health = HealthCheckRepository.get_latest_result("Linear")
    slo_health = HealthCheckRepository.get_latest_result("SLO Platform")

    context.update({
        'linear_health_status': linear_health.overall_status if linear_health else 'unknown',
        'linear_last_checked': linear_health.checked_at if linear_health else None,
        'slo_health_status': slo_health.overall_status if slo_health else 'unknown',
        'slo_last_checked': slo_health.checked_at if slo_health else None,
    })

    return context
```

#### 7. Admin Display (Extend: `requirements/admin.py`)

```python
from .models import IntegrationHealth, IntegrationHealthCheck


HEALTH_STATUS_COLORS = {
    'success': '#22c55e',
    'warning': '#f97316',
    'failure': '#ef4444',
    'unknown': '#6b7280',
}


@admin.register(IntegrationHealth)
class IntegrationHealthAdmin(ModelAdmin):
    """Admin interface for integration health checks."""

    list_display = ['integration_name', 'overall_status_badge', 'checked_at']
    list_filter = ['integration_name', 'overall_status', 'checked_at']
    readonly_fields = ['checked_at', 'check_details']

    def overall_status_badge(self, obj):
        color = HEALTH_STATUS_COLORS.get(obj.overall_status, '#6b7280')
        return format_html(
            '<span style="display: inline-block; padding: 4px 12px; '
            'border-radius: 4px; color: white; background-color: {}; '
            'font-weight: 500;">{}</span>',
            color, obj.overall_status.upper()
        )
    overall_status_badge.short_description = "Status"

    def check_details(self, obj):
        """Display individual check results."""
        checks = obj.checks.all()
        if not checks:
            return "No checks recorded"

        html_parts = []
        for check in checks:
            color = HEALTH_STATUS_COLORS.get(check.status, '#6b7280')
            html_parts.append(format_html(
                '<div style="margin-bottom: 8px;">'
                '<span style="display: inline-block; padding: 2px 8px; '
                'border-radius: 4px; color: white; background-color: {}; '
                'font-size: 11px; margin-right: 8px;">{}</span>'
                '<strong>{}</strong>: {}'
                '</div>',
                color, check.status.upper(), check.check_name, check.message
            ))

        return format_html(''.join(str(p) for p in html_parts))
    check_details.short_description = "Check Results"
```

## Multi-Check Aggregation Pattern

### Aggregation Strategy

The architecture uses a three-level aggregation hierarchy:

**Level 1: Individual Checks**
- Each `VerificationCheck` has its own status (SUCCESS, WARNING, FAILURE, UNKNOWN)
- Captures specific aspect (auth, connectivity, permissions, etc.)

**Level 2: Integration Health**
- `TestConnectionResult` aggregates multiple checks
- Overall status uses "worst case wins" logic:
  - Any FAILURE → Overall FAILURE
  - Any WARNING (no failures) → Overall WARNING
  - Any UNKNOWN (no failures/warnings) → Overall UNKNOWN
  - All SUCCESS → Overall SUCCESS

**Level 3: System-Wide Health**
- Dashboard aggregates all integrations
- Could add meta-aggregation for "all integrations healthy" indicator

### Comparison with Existing Pattern

This mirrors the existing verification status aggregation in `status.py`:

| Existing (Verification) | New (Health Checks) |
|------------------------|---------------------|
| `compute_verification_status()` | `VerificationCheck` individual result |
| `compute_unified_verification_status()` | `TestConnectionResult` aggregation |
| `update_all_unified_statuses()` | Dashboard-level aggregation |

**Key Difference:** Health checks are stateless (executed on-demand, optionally persisted), while verification status is persistent-first (computed from stored test/SLO data).

## Data Flow

### Health Check Execution Flow

```
User Action (Admin or API)
    ↓
API Endpoint (/api/integrations/{name}/test/)
    ↓
Health Checker Class (LinearHealthChecker, SLOHealthChecker)
    ↓
Execute Individual Checks (_check_authentication, _check_reachability, etc.)
    ↓
Return VerificationCheck Domain Objects
    ↓
Aggregate into TestConnectionResult
    ↓
[Optional] Repository.save_result()
    ↓
Persist to IntegrationHealth + IntegrationHealthCheck models
    ↓
Return JSON Response
```

### Dashboard Display Flow

```
User Loads Admin Dashboard
    ↓
dashboard_callback() invoked
    ↓
Repository.get_latest_result() for each integration
    ↓
Add integration_health_status to context
    ↓
Django-Unfold renders dashboard template
    ↓
Status badges displayed with colors
```

### Comparison with Existing Flows

**SLO Update Flow (existing):**
```
External Platform → POST /api/slo/status/ → Update SLO models →
update_all_slo_statuses() → Update Requirement.slo_status
```

**Health Check Flow (new):**
```
Admin/API Request → POST /api/integrations/linear/test/ →
Execute checks → Return results → [Optional] Persist to IntegrationHealth
```

**Key Difference:** Health checks are pull-based (SpecTrace initiates), while SLO/validation updates are push-based (external systems initiate).

## Integration Points with Existing Components

### 1. Models Layer (`requirements/models.py`)

**Add:**
- `IntegrationHealth` model (new table)
- `IntegrationHealthCheck` model (new table)

**No Changes To:**
- Existing `Requirement`, `SLO`, `InAppValidation` models
- Health checks are independent, no foreign keys to existing models

### 2. API Layer (`requirements/api.py`)

**Add:**
- `test_linear_connection(request)` endpoint
- `test_slo_connection(request)` endpoint
- `get_integration_health(request, integration_name)` endpoint

**Pattern Consistency:**
- Same JSON response format as existing endpoints
- Same error handling pattern
- Same `@require_http_methods` decorators

### 3. Dashboard (`requirements/dashboard.py`)

**Modify:**
- Extend `dashboard_callback()` to add integration health context variables
- Follow existing pattern of `context.update({...})`

**Display Variables Added:**
- `linear_health_status`, `linear_last_checked`
- `slo_health_status`, `slo_last_checked`
- Dashboard template can render status badges

### 4. Admin (`requirements/admin.py`)

**Add:**
- `IntegrationHealthAdmin` class
- Register with `@admin.register(IntegrationHealth)`

**Pattern Consistency:**
- Use `ModelAdmin` from `unfold.admin`
- Use same status badge pattern as existing admins
- Use same color scheme (`HEALTH_STATUS_COLORS`)

### 5. URLs (`spectrace/urls.py`)

**Add:**
```python
path('api/integrations/<str:integration_name>/test/',
     api.test_integration_connection,
     name='api-test-integration'),
path('api/integrations/<str:integration_name>/health/',
     api.get_integration_health,
     name='api-integration-health'),
```

### 6. Integration Client (`requirements/linear.py`)

**No Changes Needed:**
- `LinearClient` used as-is by `LinearHealthChecker`
- Health checker wraps client, doesn't modify it

**Potential Enhancement:**
- Add `test_connection()` method to `LinearClient` for reuse
- Not required for initial implementation

## Dependency Graph

```
New Components                      Existing Components
─────────────                      ──────────────────

domain.py
(VerificationCheck,
 TestConnectionResult)
         ↓
checkers.py ─────────────────────→ linear.py (LinearClient)
(LinearHealthChecker,
 SLOHealthChecker)
         ↓
repository.py ───────────────────→ models.py (NEW: IntegrationHealth)
(save_result,
 get_latest_result)
         ↓
api.py extensions ───────────────→ api.py (existing patterns)
(test_*_connection,
 get_integration_health)
         ↓
dashboard.py extensions ─────────→ dashboard.py (dashboard_callback)
(integration health context)
         ↓
admin.py extensions ──────────────→ admin.py (ModelAdmin pattern)
(IntegrationHealthAdmin)
```

## Build Order Recommendation

Based on dependencies and existing architecture:

### Phase 1: Foundation (No UI, Core Logic)

**1.1 Domain Objects**
- Create `requirements/health_checks/` package
- Write `domain.py` with `VerificationCheck`, `TestConnectionResult` dataclasses
- REASON: Pure Python, no dependencies, enables testing

**1.2 Health Checker Base**
- Write `checkers.py` with `HealthChecker` base class
- REASON: Establishes pattern before implementing specific checkers

**1.3 Linear Health Checker**
- Implement `LinearHealthChecker` in `checkers.py`
- REASON: Reuses existing `LinearClient`, validates pattern with real integration

**Testing Checkpoint:** Unit tests for domain objects and Linear health checker (no database needed)

### Phase 2: Persistence (Database, No UI)

**2.1 Models**
- Add `IntegrationHealth`, `IntegrationHealthCheck` to `models.py`
- Create and run migration
- REASON: Enables historical tracking

**2.2 Repository**
- Write `repository.py` with `save_result()`, `get_latest_result()`
- REASON: Abstracts persistence, enables testing with fake repository

**Testing Checkpoint:** Integration tests with database, verify persistence round-trip

### Phase 3: API Endpoints (Testable Interface)

**3.1 Test Connection Endpoint**
- Add `test_linear_connection()` to `api.py`
- Add URL route to `urls.py`
- REASON: Provides HTTP interface for testing health checks

**3.2 Get Health Status Endpoint**
- Add `get_integration_health()` to `api.py`
- Add URL route
- REASON: Allows querying latest health status

**Testing Checkpoint:** API tests, verify JSON responses, error handling

### Phase 4: Dashboard Integration (UI)

**4.1 Dashboard Context**
- Extend `dashboard_callback()` to add health status
- REASON: Provides data to dashboard template

**4.2 Dashboard Template**
- Add health status display to dashboard template (if custom template needed)
- OR: Document variables for future template customization
- REASON: Unfold may handle display automatically via context

**Testing Checkpoint:** Manual test in admin dashboard, verify status badges

### Phase 5: Admin Interface (Management UI)

**5.1 Health Check Admin**
- Add `IntegrationHealthAdmin` to `admin.py`
- REASON: Allows viewing health check history

**Testing Checkpoint:** Manual test admin pages, verify badge display

### Phase 6: Additional Integrations (Expansion)

**6.1 SLO Health Checker**
- Implement `SLOHealthChecker` in `checkers.py`
- Add corresponding API endpoint
- REASON: Repeats pattern established with Linear

**6.2 Additional Checkers**
- Database health, cache health, etc. (if needed)
- REASON: Reuses established patterns

## Alternative Patterns Considered

### Alternative 1: Django-Health-Check Library

**What:** Use `django-health-check` package with custom backends

**Pros:**
- Industry-standard package, well-maintained
- Pluggable architecture via `BaseHealthCheckBackend`
- Automatic `/ht/` endpoint with JSON/HTML responses
- HTTP 200/500 aggregation built-in

**Cons:**
- Designed for infrastructure health (DB, cache, Celery)
- Not designed for historical tracking (no persistence)
- Custom backends for integrations would need adaptation
- Doesn't fit domain object pattern used in SpecTrace

**Why Not Recommended:**
SpecTrace needs historical health check tracking and integration-specific checks (Linear API, SLO platforms), which aren't the primary use case for django-health-check. The library is optimized for monitoring infrastructure health for load balancers/orchestrators, not for building an integration dashboard.

**When to Reconsider:**
If SpecTrace needs standard infrastructure health checks (database, cache) in addition to integration checks, use django-health-check for infrastructure and the recommended pattern for integrations.

### Alternative 2: Persistent-First Pattern

**What:** Store health checks in models directly, no domain objects

**Pros:**
- Simpler, fewer layers
- No dataclass/repository separation
- Direct Django ORM usage

**Cons:**
- Couples health check logic to Django ORM
- Hard to test without database
- Doesn't match existing `status.py` pattern
- Can't execute checks without persisting results

**Why Not Recommended:**
Breaks separation of concerns established by `status.py`. Health checks should be executable independently of persistence decision (e.g., test connection without saving history).

### Alternative 3: Async Background Jobs

**What:** Run health checks via Celery/background jobs on schedule

**Pros:**
- Automatic periodic health monitoring
- No manual trigger needed
- Could alert on failures

**Cons:**
- Requires Celery/Redis infrastructure
- Adds complexity
- Doesn't provide on-demand testing (needed for admin UI)

**Why Not Recommended:**
SpecTrace doesn't currently use Celery. The milestone focuses on "test connection" functionality for admin configuration, not automated monitoring. On-demand checks are sufficient.

**When to Reconsider:**
Future milestone could add scheduled health checks, building on the foundation established here.

## Scalability Considerations

### At Current Scale (< 100 integrations)

**No concerns:**
- Health checks executed on-demand, not on every request
- Dataclass overhead negligible
- Repository pattern adds minimal abstraction cost

**Storage:**
- `IntegrationHealth` table: ~10 records/integration/day = ~1000 records/day
- With 100 integrations = 36,500 records/year (trivial for SQLite)

### At Medium Scale (100-1000 integrations)

**Considerations:**
- Add index on `IntegrationHealth.integration_name + checked_at`
- Add database cleanup (delete old health checks after 30/90 days)
- Consider caching latest health status in dashboard

**Query Optimization:**
```python
# Dashboard query with prefetch
latest_health = IntegrationHealth.objects.filter(
    integration_name="Linear"
).select_related().prefetch_related('checks').first()
```

### At Large Scale (> 1000 integrations)

**Considerations:**
- Move health check execution to background jobs (Celery)
- Cache health status in Redis
- Add dedicated health check service (microservice pattern)
- Use time-series database for health metrics (Prometheus, InfluxDB)

**Current architecture supports migration:**
- Domain objects are framework-agnostic
- Health checkers can be called from anywhere (view, Celery task, CLI)
- Repository abstracts persistence (could swap to time-series DB)

## Sources

Research based on current Django and Python architectural best practices:

- [Django Health Check Package](https://github.com/revsys/django-health-check) - Industry-standard health check patterns
- [Django Health Check Documentation](https://django-health-check.readthedocs.io/en/latest/) - Custom backend architecture
- [Medium: Production-Grade Health Check in Django](https://medium.com/@iman.rameshni/django-health-check-89fb6ad39b0c) - Best practices
- [Microservices Health Check API Pattern](https://microservices.io/patterns/observability/health-check-api.html) - Aggregation patterns
- [Baeldung: REST API Error Handling](https://www.baeldung.com/rest-api-error-handling-best-practices) - Response format patterns
- [Unfold Admin Theme](https://unfoldadmin.com/) - Dashboard integration patterns
- [Cosmic Python: Domain Modeling](https://www.cosmicpython.com/book/chapter_01_domain_model.html) - Dataclass pattern
- [Cosmic Python: Repository Pattern with Django](https://www.cosmicpython.com/book/appendix_django.html) - Repository implementation
- [O'Reilly: Architecture Patterns with Python](https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/ch01.html) - Domain objects vs models
- [Plain English: DTO in Django](https://plainenglish.io/blog/data-transfer-object-in-django-drf) - DTO pattern
- [Azure: Health Endpoint Monitoring Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring) - Health check design patterns
- [Pydantic Dataclasses](https://docs.pydantic.dev/latest/concepts/dataclasses/) - Validation patterns

All sources verified as current for 2026 best practices.
