# Integration Plan: VerificationCheck Pattern for SpecTrace

## Overview

This plan integrates the `VerificationCheck` pattern from Canary PR #35544 into SpecTrace to provide:
1. **Integration health monitoring** - test connectivity to Linear, SLO platforms, CI/CD
2. **Granular diagnostic checks** - detailed pass/fail results with error info
3. **Dashboard visibility** - integration status at a glance
4. **API endpoint** - programmatic health checks for monitoring systems

## Source Pattern Analysis (Canary PR #35544)

### Key Components

```python
# Backend dataclasses
@dataclass
class VerificationCheck:
    name: str                       # e.g., "Authenticated with Linear API"
    passed: bool                    # True/False
    details: str | None             # Human-readable context
    error_message: str | None       # Error string if failed
    response_status: int | None     # HTTP status code
    response_body: str | None       # Truncated response for debugging
    timestamp: str                  # ISO timestamp

@dataclass
class TestConnectionResult:
    success: bool                   # Overall pass/fail
    message: str                    # Summary message
    checks: list[VerificationCheck] # Individual checks
    error_details: str | None       # Additional error context
```

### Frontend TypeScript
```typescript
interface VerificationCheck {
  name: string;
  passed: boolean;
  details?: string;
  error_message?: string;
  response_status?: number;
  response_body?: string;
  timestamp?: string;
}

interface TestConnectionResult {
  success: boolean;
  message: string;
  checks: VerificationCheck[] | null;
  error_details: string | null;
}
```

### Pattern Characteristics
- **Multi-check aggregation**: Multiple named checks per integration
- **Early exit on critical failure**: Config check fails → skip connection test
- **Diagnostic info**: Response status/body for debugging
- **Timestamped**: Each check has its own timestamp
- **Truncated responses**: Long response bodies truncated to 500 chars

---

## SpecTrace Integration Points

### Current Integrations That Need Health Checks

| Integration | Purpose | Health Check Needs |
|-------------|---------|-------------------|
| Linear | Sync requirements from issues | API auth, GraphQL query |
| SLO Platform | Receive status updates | Webhook endpoint reachable |
| CI/CD | Test result imports | Can access JUnit XML |
| In-App Validation | Product validation results | Endpoint authentication |

### Existing Architecture to Extend

```
requirements/
├── api.py           # Add /api/integrations/health/ endpoint
├── linear.py        # Add test_connection() method
├── models.py        # Add IntegrationHealth model (optional)
└── integrations/    # NEW: integration health module
    ├── __init__.py
    ├── checks.py    # VerificationCheck, TestConnectionResult
    ├── linear.py    # LinearHealthChecker
    ├── slo.py       # SLOHealthChecker
    └── views.py     # IntegrationHealthView
```

---

## Implementation Plan

### Phase 1: Core Check Infrastructure

**Goal**: Create reusable VerificationCheck pattern

**Files to create**:

#### 1. `requirements/integrations/__init__.py`
```python
"""Integration health checking module."""
from .checks import VerificationCheck, TestConnectionResult
```

#### 2. `requirements/integrations/checks.py`
```python
"""Core verification check dataclasses."""
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: str | None, max_length: int = 500) -> str | None:
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


@dataclass
class VerificationCheck:
    """Individual verification checkpoint."""
    name: str
    passed: bool
    details: str | None = None
    error_message: str | None = None
    response_status: int | None = None
    response_body: str | None = None
    timestamp: str = field(default_factory=_get_timestamp)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'passed': self.passed,
            'details': self.details,
            'error_message': self.error_message,
            'response_status': self.response_status,
            'response_body': self.response_body,
            'timestamp': self.timestamp,
        }


@dataclass
class TestConnectionResult:
    """Aggregated result from testing an integration."""
    success: bool
    message: str
    checks: list[VerificationCheck] | None = None
    error_details: str | None = None

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'message': self.message,
            'checks': [c.to_dict() for c in self.checks] if self.checks else None,
            'error_details': self.error_details,
        }
```

### Phase 2: Linear Integration Checker

**Goal**: Test Linear API connectivity

#### 3. `requirements/integrations/linear.py`
```python
"""Linear integration health checker."""
import requests
from django.conf import settings

from .checks import TestConnectionResult, VerificationCheck, _truncate


class LinearHealthChecker:
    """Test connectivity to Linear API."""

    API_URL = "https://api.linear.app/graphql"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or getattr(settings, 'LINEAR_API_KEY', None)

    def test_connection(self) -> TestConnectionResult:
        """Test Linear API connectivity."""
        checks: list[VerificationCheck] = []

        # Check 1: API key configured
        if not self.api_key:
            return TestConnectionResult(
                success=False,
                message="Linear is not configured",
                checks=[VerificationCheck(
                    name="Linear API key configured",
                    passed=False,
                    details="No LINEAR_API_KEY in settings",
                    error_message="API key not found",
                )],
            )

        checks.append(VerificationCheck(
            name="Linear API key configured",
            passed=True,
            details="API key found in settings",
        ))

        # Check 2: API authentication
        try:
            response = requests.post(
                self.API_URL,
                json={'query': '{ viewer { id name } }'},
                headers={
                    'Authorization': self.api_key,
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    checks.append(VerificationCheck(
                        name="Authenticated with Linear API",
                        passed=False,
                        details="GraphQL errors in response",
                        error_message=str(data['errors']),
                        response_status=response.status_code,
                    ))
                else:
                    viewer = data.get('data', {}).get('viewer', {})
                    checks.append(VerificationCheck(
                        name="Authenticated with Linear API",
                        passed=True,
                        details=f"Connected as: {viewer.get('name', 'Unknown')}",
                        response_status=response.status_code,
                    ))
            else:
                checks.append(VerificationCheck(
                    name="Authenticated with Linear API",
                    passed=False,
                    details="Authentication failed",
                    error_message=f"HTTP {response.status_code}",
                    response_status=response.status_code,
                    response_body=_truncate(response.text),
                ))

        except requests.RequestException as e:
            checks.append(VerificationCheck(
                name="Authenticated with Linear API",
                passed=False,
                details="Connection failed",
                error_message=str(e),
            ))

        all_passed = all(c.passed for c in checks)
        return TestConnectionResult(
            success=all_passed,
            message="All checks passed" if all_passed else "Some checks failed",
            checks=checks,
        )
```

### Phase 3: SLO Platform Checker

#### 4. `requirements/integrations/slo.py`
```python
"""SLO platform integration health checker."""
import requests
from django.conf import settings

from .checks import TestConnectionResult, VerificationCheck, _truncate


class SLOHealthChecker:
    """Test connectivity to SLO/observability platform."""

    def __init__(self, endpoint_url: str | None = None):
        self.endpoint_url = endpoint_url or getattr(settings, 'SLO_PLATFORM_URL', None)

    def test_connection(self) -> TestConnectionResult:
        """Test SLO platform connectivity."""
        checks: list[VerificationCheck] = []

        # Check 1: Endpoint configured
        if not self.endpoint_url:
            return TestConnectionResult(
                success=False,
                message="SLO platform is not configured",
                checks=[VerificationCheck(
                    name="SLO endpoint configured",
                    passed=False,
                    details="No SLO_PLATFORM_URL in settings",
                    error_message="Endpoint URL not found",
                )],
            )

        checks.append(VerificationCheck(
            name="SLO endpoint configured",
            passed=True,
            details=f"Endpoint: {self.endpoint_url}",
        ))

        # Check 2: Health endpoint reachable
        health_url = f"{self.endpoint_url.rstrip('/')}/health"
        try:
            response = requests.get(health_url, timeout=10)

            if response.status_code == 200:
                checks.append(VerificationCheck(
                    name="SLO platform health check",
                    passed=True,
                    details="Platform is healthy",
                    response_status=response.status_code,
                ))
            else:
                checks.append(VerificationCheck(
                    name="SLO platform health check",
                    passed=False,
                    details="Unexpected response",
                    response_status=response.status_code,
                    response_body=_truncate(response.text),
                ))

        except requests.RequestException as e:
            checks.append(VerificationCheck(
                name="SLO platform health check",
                passed=False,
                details="Connection failed",
                error_message=str(e),
            ))

        all_passed = all(c.passed for c in checks)
        return TestConnectionResult(
            success=all_passed,
            message="All checks passed" if all_passed else "Some checks failed",
            checks=checks,
        )
```

### Phase 4: API Endpoint

#### 5. Update `requirements/api.py`
```python
# Add to existing api.py

from .integrations.linear import LinearHealthChecker
from .integrations.slo import SLOHealthChecker


@csrf_exempt
@require_http_methods(["POST"])
def test_integration_connection(request):
    """Test connectivity to an integration.

    POST /api/integrations/health/

    Request body:
    {
        "integration": "linear"  // linear, slo, cicd
    }

    Response:
    {
        "success": true,
        "message": "All checks passed",
        "checks": [
            {
                "name": "Linear API key configured",
                "passed": true,
                "details": "API key found in settings",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            ...
        ]
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    integration = data.get('integration', '').lower()

    checkers = {
        'linear': LinearHealthChecker,
        'slo': SLOHealthChecker,
    }

    checker_class = checkers.get(integration)
    if not checker_class:
        return JsonResponse({
            'success': False,
            'error': f'Unknown integration: {integration}',
            'available': list(checkers.keys()),
        }, status=400)

    checker = checker_class()
    result = checker.test_connection()

    return JsonResponse(result.to_dict())


@require_http_methods(["GET"])
def get_all_integration_health(request):
    """Get health status of all configured integrations.

    GET /api/integrations/health/

    Response:
    {
        "integrations": {
            "linear": {"success": true, "message": "...", "checks": [...]},
            "slo": {"success": false, "message": "...", "checks": [...]}
        },
        "overall_healthy": false
    }
    """
    results = {}

    # Test all integrations
    checkers = {
        'linear': LinearHealthChecker,
        'slo': SLOHealthChecker,
    }

    for name, checker_class in checkers.items():
        checker = checker_class()
        result = checker.test_connection()
        results[name] = result.to_dict()

    overall_healthy = all(r['success'] for r in results.values())

    return JsonResponse({
        'integrations': results,
        'overall_healthy': overall_healthy,
    })
```

#### 6. Update `spectrace/urls.py`
```python
# Add to urlpatterns
path('api/integrations/health/', api.test_integration_connection, name='api-integration-health'),
path('api/integrations/health/all/', api.get_all_integration_health, name='api-integration-health-all'),
```

### Phase 5: Dashboard Integration

#### 7. Update `requirements/dashboard.py`
```python
# Add integration health to dashboard callback

def dashboard_callback(request, context):
    """Custom dashboard callback for Unfold admin."""
    # ... existing code ...

    # Add integration health summary
    from .integrations.linear import LinearHealthChecker
    from .integrations.slo import SLOHealthChecker

    integration_health = {}
    for name, checker_class in [('linear', LinearHealthChecker), ('slo', SLOHealthChecker)]:
        try:
            result = checker_class().test_connection()
            integration_health[name] = {
                'healthy': result.success,
                'message': result.message,
            }
        except Exception:
            integration_health[name] = {
                'healthy': False,
                'message': 'Check failed',
            }

    context.update({
        # ... existing context ...
        'integration_health': integration_health,
    })

    return context
```

### Phase 6: Admin UI (Optional Enhancement)

Add an "Integration Health" section to the admin dashboard template showing:
- Status icons for each integration (green/red)
- "Test Connection" buttons
- Expandable check details
- Last checked timestamp

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `requirements/integrations/__init__.py` | Create | Module init |
| `requirements/integrations/checks.py` | Create | Core dataclasses |
| `requirements/integrations/linear.py` | Create | Linear health checker |
| `requirements/integrations/slo.py` | Create | SLO health checker |
| `requirements/api.py` | Modify | Add health endpoints |
| `spectrace/urls.py` | Modify | Add URL routes |
| `requirements/dashboard.py` | Modify | Add health to dashboard |
| `requirements/tests/test_integration_health.py` | Create | Tests for new functionality |

---

## Testing Strategy

```python
# requirements/tests/test_integration_health.py

import pytest
from unittest.mock import patch, Mock

from requirements.integrations.checks import VerificationCheck, TestConnectionResult
from requirements.integrations.linear import LinearHealthChecker


class TestVerificationCheck:
    def test_to_dict(self):
        check = VerificationCheck(
            name="Test check",
            passed=True,
            details="All good",
        )
        d = check.to_dict()
        assert d['name'] == "Test check"
        assert d['passed'] is True
        assert 'timestamp' in d


class TestLinearHealthChecker:
    def test_no_api_key_fails(self):
        checker = LinearHealthChecker(api_key=None)
        result = checker.test_connection()

        assert result.success is False
        assert len(result.checks) == 1
        assert result.checks[0].name == "Linear API key configured"
        assert result.checks[0].passed is False

    @patch('requirements.integrations.linear.requests.post')
    def test_successful_auth(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {'viewer': {'id': '123', 'name': 'Test User'}}
        }
        mock_post.return_value = mock_response

        checker = LinearHealthChecker(api_key='lin_api_test')
        result = checker.test_connection()

        assert result.success is True
        assert len(result.checks) == 2
        assert all(c.passed for c in result.checks)

    @patch('requirements.integrations.linear.requests.post')
    def test_auth_failure(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_post.return_value = mock_response

        checker = LinearHealthChecker(api_key='lin_api_invalid')
        result = checker.test_connection()

        assert result.success is False
        failed = [c for c in result.checks if not c.passed]
        assert len(failed) == 1
        assert failed[0].response_status == 401
```

---

## Benefits

1. **Diagnostic visibility**: Users can see exactly which check failed and why
2. **Proactive monitoring**: Dashboard shows integration health at a glance
3. **API-driven**: External monitoring systems can poll health endpoints
4. **Extensible**: Easy to add new integrations (CI/CD, Slack, etc.)
5. **Consistent pattern**: Same structure as Canary for cross-project familiarity

---

## Future Extensions

1. **CI/CD Integration Checker** - verify GitHub Actions/CircleCI webhook connectivity
2. **Webhook Validation** - test that incoming webhook signatures are correct
3. **Scheduled Health Checks** - Django-Q task to run checks periodically
4. **Health History** - store check results in database for trending
5. **Alerting** - notify when integrations become unhealthy
