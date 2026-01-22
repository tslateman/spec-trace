# Phase 6: API Endpoints - Research

**Researched:** 2026-01-21
**Domain:** Django REST API endpoints, caching, JSON responses
**Confidence:** HIGH

## Summary

This phase implements REST API endpoints for the Linear integration health check system. The foundation work from Phase 5 provides `verify_linear_connection()` which returns `TestConnectionResult` dataclasses. Phase 6 exposes this functionality via two endpoints: POST for triggering fresh health checks and GET for retrieving cached status.

The established approach uses Django's native function-based views with `JsonResponse` and `dataclasses.asdict()` for serialization. Caching uses Django's low-level cache API (`cache.get`/`cache.set`) to respect Linear's 5,000 requests/hour rate limit. The existing `api.py` file already demonstrates the project's patterns for JSON endpoints.

**Primary recommendation:** Use Django's native function-based views with `@require_http_methods` decorator, `dataclasses.asdict()` for JSON serialization, and Django's low-level cache API with a 5-minute TTL for rate limit compliance. Implement "worst case wins" status aggregation (healthy/degraded/unhealthy) based on individual check results.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django cache | 5.2+ (stdlib) | Results caching | Already configured, low-level API sufficient, no additional dependencies |
| dataclasses.asdict | stdlib | JSON serialization | Converts Phase 5 dataclasses to dicts for JsonResponse |
| django.http.JsonResponse | Django stdlib | JSON responses | Existing pattern in api.py, handles content-type headers |
| django.views.decorators.http | Django stdlib | HTTP method restriction | require_http_methods, require_GET for REST semantics |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django.views.decorators.csrf | Django stdlib | CSRF exemption | @csrf_exempt for API endpoints (existing pattern) |
| json | stdlib | Request body parsing | Parsing POST body (existing pattern in api.py) |
| django.conf.settings | Django stdlib | Configuration access | LINEAR_API_KEY, LINEAR_WORKSPACE, LINEAR_TEAM |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Function-based views | Django REST Framework | Overkill for 2 simple endpoints, adds dependency |
| Django cache | Redis | Unnecessary complexity for single-server SQLite setup |
| dataclasses.asdict() | Pydantic/DRF serializers | Phase 5 dataclasses already work with asdict() |
| Custom caching | django-cacheops | Low-level cache API is simpler for this use case |

**Installation:**
```bash
# No additional dependencies needed - all Django stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
spectrace/requirements/
    api.py             # Add health check endpoints here (existing file)
    health.py          # verify_linear_connection() from Phase 5
    models.py          # No changes needed (health data is transient)
```

### Pattern 1: POST Endpoint for Fresh Health Check
**What:** Trigger a fresh health check and return results
**When to use:** User explicitly requests connection test
**Example:**
```python
# Source: Existing pattern from api.py + Phase 5 health.py
from dataclasses import asdict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.cache import cache

from .health import verify_linear_connection

HEALTH_CACHE_KEY = 'linear_health_status'
HEALTH_CACHE_TIMEOUT = 300  # 5 minutes

@csrf_exempt
@require_http_methods(["POST"])
def test_linear_connection(request):
    """Trigger fresh Linear health check.

    POST /api/integrations/linear/test-connection

    Response:
    {
        "success": true,
        "message": "All checks passed",
        "status": "healthy",
        "checks": [
            {
                "name": "Configuration",
                "passed": true,
                "details": "...",
                "timestamp": "2026-01-21T..."
            },
            ...
        ]
    }
    """
    api_key = getattr(settings, 'LINEAR_API_KEY', '')
    workspace = getattr(settings, 'LINEAR_WORKSPACE', '')
    team = getattr(settings, 'LINEAR_TEAM', '')

    result = verify_linear_connection(api_key, workspace, team)

    # Compute overall status (worst case wins)
    status = compute_overall_status(result)

    # Cache the result
    response_data = asdict(result)
    response_data['status'] = status
    cache.set(HEALTH_CACHE_KEY, response_data, timeout=HEALTH_CACHE_TIMEOUT)

    return JsonResponse(response_data)
```

### Pattern 2: GET Endpoint for Cached Status
**What:** Return cached health status without making API calls
**When to use:** Dashboard polling, load balancer health checks
**Example:**
```python
# Source: Django cache documentation + existing api.py patterns
@require_http_methods(["GET"])
def get_linear_health(request):
    """Get cached Linear health status.

    GET /api/integrations/linear/health

    Response:
    {
        "success": true,
        "message": "All checks passed",
        "status": "healthy",
        "checks": [...],
        "cached": true,
        "cache_age_seconds": 45
    }

    Returns 503 if no cached status available (never tested).
    """
    cached = cache.get(HEALTH_CACHE_KEY)

    if cached is None:
        return JsonResponse({
            'success': False,
            'message': 'No health check data available. Run POST /api/integrations/linear/test-connection first.',
            'status': 'unknown'
        }, status=503)

    cached['cached'] = True
    return JsonResponse(cached)
```

### Pattern 3: Overall Status Aggregation (Worst Case Wins)
**What:** Compute healthy/degraded/unhealthy from individual checks
**When to use:** Computing summary status for API response
**Example:**
```python
# Source: HEALTH-05 requirement specification
def compute_overall_status(result) -> str:
    """Compute overall status from TestConnectionResult.

    Status hierarchy (worst case wins):
    - unhealthy: Any check failed
    - degraded: Reserved for partial failures (future extension)
    - healthy: All checks passed

    Args:
        result: TestConnectionResult from verify_linear_connection()

    Returns:
        'healthy', 'degraded', or 'unhealthy'
    """
    if not result.success:
        return 'unhealthy'

    if result.checks is None:
        return 'unhealthy'

    if not all(check.passed for check in result.checks):
        return 'unhealthy'

    return 'healthy'
```

### Pattern 4: URL Configuration
**What:** REST-style URL paths for health endpoints
**When to use:** Adding endpoints to urls.py
**Example:**
```python
# Source: Existing urls.py patterns
from django.urls import path
from requirements import api

urlpatterns = [
    # ... existing patterns ...

    # Linear integration health endpoints
    path('api/integrations/linear/test-connection', api.test_linear_connection, name='api-linear-test-connection'),
    path('api/integrations/linear/health', api.get_linear_health, name='api-linear-health'),
]
```

### Anti-Patterns to Avoid
- **Don't use DRF for simple endpoints:** Function-based views with JsonResponse are sufficient
- **Don't cache in the view function:** Use Django's cache framework, not instance variables
- **Don't expose raw dataclass without status field:** Add computed 'status' field to response
- **Don't skip CSRF exemption on POST:** API endpoints need @csrf_exempt
- **Don't make GET endpoint trigger health checks:** GET should only return cached data

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON serialization | Manual dict building | `dataclasses.asdict()` | Handles nested dataclasses, respects field factories |
| Response caching | Global variables | `django.core.cache` | Thread-safe, configurable backend, TTL support |
| HTTP method restriction | Manual method checking | `@require_http_methods` | Returns proper 405 response, handles OPTIONS |
| Content-Type header | Manual header setting | `JsonResponse` | Sets application/json automatically |
| Cache key management | String concatenation | Constant with prefix | Prevents key collisions, easy to find/clear |

**Key insight:** Django provides everything needed for simple REST endpoints. Adding DRF or custom frameworks adds complexity without benefit for this use case.

## Common Pitfalls

### Pitfall 1: Cache Race Conditions
**What goes wrong:** Multiple simultaneous health check requests all hit Linear API
**Why it happens:** Check-then-set pattern without locking
**How to avoid:** Accept that occasional duplicate requests are OK (rate limit is 5K/hr), or use `cache.add()` for lock
**Warning signs:** Linear rate limit errors during high traffic

### Pitfall 2: Missing CSRF Exemption
**What goes wrong:** POST returns 403 Forbidden
**Why it happens:** Django CSRF middleware blocks API requests without token
**How to avoid:** Use `@csrf_exempt` decorator (existing pattern in api.py)
**Warning signs:** "CSRF verification failed" error in POST response

### Pitfall 3: Serialization of Dataclass Fails
**What goes wrong:** TypeError when passing dataclass to JsonResponse
**Why it happens:** JsonResponse doesn't handle dataclasses natively
**How to avoid:** Use `asdict(result)` to convert dataclass to dict first
**Warning signs:** "Object of type TestConnectionResult is not JSON serializable"

### Pitfall 4: Cache Returns None vs Empty
**What goes wrong:** Treating None cache result same as empty/failed check
**Why it happens:** `cache.get()` returns None for missing keys
**How to avoid:** Explicitly check for None and return 503 with helpful message
**Warning signs:** Empty responses or incorrect "healthy" status when never tested

### Pitfall 5: Status Field Missing from Response
**What goes wrong:** Frontend can't determine overall health status
**Why it happens:** `asdict()` only includes dataclass fields, not computed values
**How to avoid:** Add 'status' key to response dict after asdict() conversion
**Warning signs:** API response has success/checks but no 'status' field

### Pitfall 6: Linear Rate Limit Exceeded
**What goes wrong:** Health checks fail with rate limit errors
**Why it happens:** Too many fresh checks triggered without caching
**How to avoid:** Cache results for 5 minutes (5K req/hr = 83 req/min max, 5-min cache = 12 req/hr)
**Warning signs:** HTTP 400 with RATELIMITED error code from Linear

### Pitfall 7: Settings Not Configured
**What goes wrong:** Health check fails with "not configured" even when settings exist
**Why it happens:** Using `settings.LINEAR_API_KEY` instead of `getattr(settings, 'LINEAR_API_KEY', '')`
**How to avoid:** Use getattr with default empty string (existing pattern)
**Warning signs:** AttributeError when accessing settings

## Code Examples

Verified patterns from official sources:

### Complete API Module Extension
```python
# Source: Existing api.py patterns + Django cache documentation
"""API endpoints for Linear integration health checks."""
from dataclasses import asdict

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .health import verify_linear_connection

# Cache configuration
HEALTH_CACHE_KEY = 'linear:health_status'
HEALTH_CACHE_TIMEOUT = 300  # 5 minutes - respect Linear's 5K req/hr limit


def _compute_overall_status(result) -> str:
    """Compute overall status from TestConnectionResult (worst case wins).

    Returns:
        'healthy' - All checks passed
        'unhealthy' - Any check failed or no checks run
    """
    if not result.success:
        return 'unhealthy'
    if result.checks is None:
        return 'unhealthy'
    if not all(check.passed for check in result.checks):
        return 'unhealthy'
    return 'healthy'


@csrf_exempt
@require_http_methods(["POST"])
def test_linear_connection_endpoint(request):
    """Trigger fresh Linear health check.

    POST /api/integrations/linear/test-connection

    Response (200):
    {
        "success": true,
        "message": "All checks passed",
        "status": "healthy",
        "checks": [
            {
                "name": "Configuration",
                "passed": true,
                "details": "API key present, workspace: ..., team: ...",
                "error_message": null,
                "response_status": null,
                "response_body": null,
                "timestamp": "2026-01-21T10:30:00.000000Z"
            },
            {
                "name": "Authentication",
                "passed": true,
                "details": "Authenticated as User (user@example.com)",
                "response_status": 200,
                "timestamp": "..."
            },
            {
                "name": "Permissions",
                "passed": true,
                "details": "Read access to issues endpoint confirmed",
                "response_status": 200,
                "timestamp": "..."
            }
        ],
        "error_details": null
    }
    """
    # Get Linear config from settings
    api_key = getattr(settings, 'LINEAR_API_KEY', '')
    workspace = getattr(settings, 'LINEAR_WORKSPACE', '')
    team = getattr(settings, 'LINEAR_TEAM', '')

    # Run fresh health check
    result = verify_linear_connection(api_key, workspace, team)

    # Convert to dict and add computed status
    response_data = asdict(result)
    response_data['status'] = _compute_overall_status(result)

    # Cache for rate limiting
    cache.set(HEALTH_CACHE_KEY, response_data, timeout=HEALTH_CACHE_TIMEOUT)

    return JsonResponse(response_data)


@require_http_methods(["GET"])
def get_linear_health_endpoint(request):
    """Get cached Linear health status without triggering new check.

    GET /api/integrations/linear/health

    Response (200 - cached status available):
    {
        "success": true,
        "message": "All checks passed",
        "status": "healthy",
        "checks": [...],
        "error_details": null,
        "cached": true
    }

    Response (503 - no cached status):
    {
        "success": false,
        "message": "No health check data available. Trigger a check first.",
        "status": "unknown"
    }
    """
    cached = cache.get(HEALTH_CACHE_KEY)

    if cached is None:
        return JsonResponse({
            'success': False,
            'message': 'No health check data available. Trigger a check with POST /api/integrations/linear/test-connection first.',
            'status': 'unknown'
        }, status=503)

    # Mark as cached (don't modify original cache entry)
    response_data = dict(cached)
    response_data['cached'] = True

    return JsonResponse(response_data)
```

### URL Configuration
```python
# Source: Existing urls.py patterns
# Add to spectrace/spectrace/urls.py

from requirements import api

urlpatterns = [
    # ... existing patterns ...

    # Linear integration health check endpoints
    path('api/integrations/linear/test-connection', api.test_linear_connection_endpoint, name='api-linear-test-connection'),
    path('api/integrations/linear/health', api.get_linear_health_endpoint, name='api-linear-health'),
]
```

### Test Examples
```python
# Source: Existing test_api.py patterns
"""Tests for Linear health check API endpoints."""
import json
from unittest.mock import patch, Mock

import pytest
from django.test import Client


@pytest.fixture
def client():
    """Django test client."""
    return Client()


class TestLinearTestConnectionEndpoint:
    """Tests for POST /api/integrations/linear/test-connection"""

    @pytest.mark.django_db
    def test_returns_healthy_when_all_checks_pass(self, client, settings):
        """Successful connection returns status='healthy'."""
        settings.LINEAR_API_KEY = 'lin_api_test123'
        settings.LINEAR_WORKSPACE = 'test-workspace'
        settings.LINEAR_TEAM = 'test-team'

        with patch('requirements.api.verify_linear_connection') as mock_verify:
            from requirements.health import TestConnectionResult, VerificationCheck
            mock_verify.return_value = TestConnectionResult(
                success=True,
                message="All checks passed",
                checks=[
                    VerificationCheck(name="Configuration", passed=True),
                    VerificationCheck(name="Authentication", passed=True),
                    VerificationCheck(name="Permissions", passed=True),
                ]
            )

            response = client.post('/api/integrations/linear/test-connection')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['status'] == 'healthy'
        assert len(data['checks']) == 3

    @pytest.mark.django_db
    def test_returns_unhealthy_when_check_fails(self, client, settings):
        """Failed check returns status='unhealthy'."""
        settings.LINEAR_API_KEY = 'lin_api_test123'
        settings.LINEAR_WORKSPACE = 'test-workspace'
        settings.LINEAR_TEAM = 'test-team'

        with patch('requirements.api.verify_linear_connection') as mock_verify:
            from requirements.health import TestConnectionResult, VerificationCheck
            mock_verify.return_value = TestConnectionResult(
                success=False,
                message="Authentication failed",
                checks=[
                    VerificationCheck(name="Configuration", passed=True),
                    VerificationCheck(name="Authentication", passed=False, error_message="Invalid API key"),
                ]
            )

            response = client.post('/api/integrations/linear/test-connection')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert data['status'] == 'unhealthy'

    @pytest.mark.django_db
    def test_caches_result(self, client, settings):
        """Health check result is cached."""
        settings.LINEAR_API_KEY = 'lin_api_test123'
        settings.LINEAR_WORKSPACE = 'test-workspace'
        settings.LINEAR_TEAM = 'test-team'

        with patch('requirements.api.verify_linear_connection') as mock_verify:
            from requirements.health import TestConnectionResult, VerificationCheck
            mock_verify.return_value = TestConnectionResult(
                success=True,
                message="All checks passed",
                checks=[VerificationCheck(name="Configuration", passed=True)]
            )

            client.post('/api/integrations/linear/test-connection')

        # GET should return cached result
        response = client.get('/api/integrations/linear/health')
        assert response.status_code == 200
        data = response.json()
        assert data['cached'] is True

    @pytest.mark.django_db
    def test_only_allows_post(self, client):
        """GET request returns 405."""
        response = client.get('/api/integrations/linear/test-connection')
        assert response.status_code == 405


class TestLinearHealthEndpoint:
    """Tests for GET /api/integrations/linear/health"""

    @pytest.mark.django_db
    def test_returns_503_when_no_cache(self, client):
        """No cached status returns 503 with helpful message."""
        from django.core.cache import cache
        cache.delete('linear:health_status')

        response = client.get('/api/integrations/linear/health')

        assert response.status_code == 503
        data = response.json()
        assert data['success'] is False
        assert data['status'] == 'unknown'
        assert 'POST' in data['message']

    @pytest.mark.django_db
    def test_returns_cached_status(self, client):
        """Returns cached status when available."""
        from django.core.cache import cache
        cache.set('linear:health_status', {
            'success': True,
            'message': 'All checks passed',
            'status': 'healthy',
            'checks': []
        })

        response = client.get('/api/integrations/linear/health')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['status'] == 'healthy'
        assert data['cached'] is True

    @pytest.mark.django_db
    def test_only_allows_get(self, client):
        """POST request returns 405."""
        response = client.post('/api/integrations/linear/health')
        assert response.status_code == 405
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DRF for all APIs | Function-based views for simple endpoints | Django 4.0+ | Simpler code, fewer dependencies |
| Manual JSON building | dataclasses.asdict() | Python 3.7+ | Type-safe, automatic serialization |
| Global variable caching | django.core.cache | Always preferred | Thread-safe, configurable backends |
| Polling external APIs | Caching with TTL | Standard practice | Respects rate limits, faster responses |
| Single health boolean | Granular checks + aggregation | Modern observability | Better debugging, detailed diagnostics |

**Deprecated/outdated:**
- **cache_page decorator for API responses:** Caches whole response including headers, not suitable for dynamic health checks
- **Manual Content-Type headers:** JsonResponse handles this automatically

## Open Questions

Things that couldn't be fully resolved:

1. **Cache backend selection**
   - What we know: Django default is LocMemCache (in-memory, per-process)
   - What's unclear: Whether multi-process deployments need shared cache (Redis)
   - Recommendation: Start with default LocMemCache (single-server SQLite setup), document upgrade path to Redis if needed

2. **Cache key versioning**
   - What we know: Django cache supports key versioning and prefixes
   - What's unclear: Whether we need versioning for health check data
   - Recommendation: Use simple namespaced key (`linear:health_status`), add versioning only if cache invalidation becomes an issue

3. **Authentication for API endpoints**
   - What we know: Existing endpoints in api.py don't require authentication
   - What's unclear: Whether health check endpoints should require auth
   - Recommendation: Keep unauthenticated for consistency with existing endpoints, document security implications

## Sources

### Primary (HIGH confidence)
- [Django Cache Framework](https://docs.djangoproject.com/en/5.2/topics/cache/) - Official Django caching documentation
- [Django View Decorators](https://docs.djangoproject.com/en/5.2/topics/http/decorators/) - HTTP method decorators
- [Linear Rate Limiting](https://linear.app/developers/rate-limiting) - 5,000 requests/hour limit
- Existing codebase: `api.py`, `health.py`, `urls.py` - Established project patterns

### Secondary (MEDIUM confidence)
- [Django REST Framework Views](https://www.django-rest-framework.org/api-guide/views/) - Function-based view patterns (not using DRF but patterns apply)
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) - asdict() behavior

### Tertiary (LOW confidence)
- [Django Health Check Package](https://django-health-check.readthedocs.io/) - Health check patterns (not using package but patterns inform design)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All Django stdlib, no new dependencies
- Architecture: HIGH - Follows existing api.py patterns exactly
- Pitfalls: HIGH - Based on Django documentation and common patterns

**Research date:** 2026-01-21
**Valid until:** 2026-02-21 (30 days - stable Django patterns)
