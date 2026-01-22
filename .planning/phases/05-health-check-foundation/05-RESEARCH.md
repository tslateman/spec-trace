# Phase 5: Health Check Foundation - Research

**Researched:** 2026-01-21
**Domain:** API health checks, dataclass design, GraphQL validation
**Confidence:** HIGH

## Summary

This phase implements granular diagnostic health checks for Linear integration using Python dataclasses. The pattern follows industry-standard health check architectures where individual checks (configuration, authentication, permissions) are aggregated into a comprehensive result object.

The established approach uses standard library dataclasses with field factories for auto-generated timestamps, synchronous API validation to avoid Django async complexity, and careful sanitization of error responses to prevent credential exposure. The codebase already follows similar patterns in `status.py` (computation separated from persistence) and `api.py` (JSON response structures).

**Primary recommendation:** Use standard library dataclasses with explicit field definitions, implement granular checks as independent functions that return VerificationCheck instances, and sanitize all error responses before including them in check results.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | stdlib (3.7+) | Data containers | Zero dependencies, perfect for simple structured data without validation overhead |
| requests | 2.32+ | HTTP client | Already in use (linear.py), mature exception handling, session support |
| datetime | stdlib | Timestamps | ISO 8601 support via isoformat(), timezone-aware, standard for API responses |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django.utils.timezone | Django stdlib | Timezone-aware datetimes | When persisting timestamps (already used in api.py) |
| typing | stdlib | Type hints | For Optional, Union types in dataclass fields |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dataclasses | Pydantic dataclasses | Adds dependency for auto-validation we don't need (checks validate themselves) |
| dataclasses | dict/TypedDict | Loses auto-generated __init__, __repr__, and IDE support |
| requests | httpx | Async support unnecessary (synchronous checks avoid Django async/timeout issues) |

**Installation:**
```bash
# No additional dependencies needed - all stdlib except requests (already present)
```

## Architecture Patterns

### Recommended Project Structure
```
spectrace/requirements/
├── linear.py          # Existing LinearClient
├── health.py          # NEW: Dataclasses + check functions
├── api.py             # Existing REST endpoints (add health endpoint)
└── models.py          # Existing (no health check models - use dataclasses)
```

### Pattern 1: Dataclass with Auto-Generated Timestamps
**What:** Use field(default_factory=...) for dynamic timestamp generation
**When to use:** Any field that should be computed per-instance (timestamps, UUIDs)
**Example:**
```python
# Source: https://docs.python.org/3/library/dataclasses.html
from dataclasses import dataclass, field
from datetime import datetime

def _get_timestamp() -> str:
    """Generate ISO 8601 timestamp in UTC."""
    return datetime.utcnow().isoformat() + 'Z'

@dataclass
class VerificationCheck:
    name: str
    passed: bool
    details: str | None = None
    error_message: str | None = None
    response_status: int | None = None
    response_body: str | None = None
    timestamp: str = field(default_factory=_get_timestamp)
```

**Why this pattern:**
- Each instance gets unique timestamp (not shared across instances)
- default_factory calls function at instantiation time
- ISO 8601 format enables lexicographic sorting and JSON serialization

### Pattern 2: Aggregation Dataclass
**What:** Container dataclass that holds list of check results
**When to use:** When multiple granular checks need to be combined into single response
**Example:**
```python
@dataclass
class TestConnectionResult:
    success: bool
    message: str
    checks: list[VerificationCheck] | None = None
    error_details: str | None = None
```

**Why this pattern:**
- success is boolean summary (all checks passed)
- message is human-readable summary for UI
- checks provides granular diagnostics for debugging
- error_details for catastrophic failures (network timeout, malformed config)

### Pattern 3: Granular Check Functions
**What:** Independent functions that validate one aspect and return VerificationCheck
**When to use:** Each validation concern (config, auth, permissions)
**Example:**
```python
def check_configuration(api_key: str, workspace: str, team: str) -> VerificationCheck:
    """Validate Linear configuration presence."""
    if not api_key:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY not configured"
        )

    if not api_key.startswith('lin_api_'):
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY does not match expected format"
        )

    # Validate workspace, team presence...
    return VerificationCheck(
        name="Configuration",
        passed=True,
        details=f"API key present, workspace: {workspace}, team: {team}"
    )
```

**Why this pattern:**
- Each check is independent and testable
- Early-return on failure (don't make API calls with invalid config)
- Returns consistent VerificationCheck structure

### Pattern 4: Authentication Check with API Request
**What:** Make actual API request to verify token validity
**When to use:** After configuration check passes
**Example:**
```python
def check_authentication(client: LinearClient) -> VerificationCheck:
    """Verify Linear API token with viewer query."""
    try:
        # Viewer query validates authentication
        result = client._execute_query("""
            query Me {
                viewer {
                    id
                    name
                    email
                }
            }
        """)

        viewer = result.get('viewer', {})
        return VerificationCheck(
            name="Authentication",
            passed=True,
            details=f"Authenticated as {viewer.get('name')} ({viewer.get('email')})",
            response_status=200
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Authentication failed",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text)
        )
    except Exception as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}",
        )
```

**Why this pattern:**
- Uses GraphQL viewer query (standard for "who am I" checks)
- Captures HTTP status code and sanitized response
- Differentiates HTTP errors from network/timeout errors

### Pattern 5: Permissions Check
**What:** Verify read access to required endpoints
**When to use:** After authentication check passes
**Example:**
```python
def check_permissions(client: LinearClient) -> VerificationCheck:
    """Verify read access to issues endpoint."""
    try:
        # Try to fetch one issue to verify permissions
        result = client._execute_query("""
            query TestIssueAccess {
                issues(first: 1) {
                    nodes {
                        id
                    }
                }
            }
        """)

        return VerificationCheck(
            name="Permissions",
            passed=True,
            details="Read access to issues endpoint confirmed",
            response_status=200
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Insufficient permissions",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text)
        )
```

### Pattern 6: Response Sanitization
**What:** Remove API keys and sensitive data from error responses before storing
**When to use:** Always, when capturing response bodies for debugging
**Example:**
```python
def _sanitize_response(response_text: str, max_length: int = 500) -> str:
    """Sanitize API response by removing credentials and truncating.

    Args:
        response_text: Raw response body
        max_length: Maximum length of sanitized response

    Returns:
        Sanitized response string safe for logging/storage
    """
    import re

    # Truncate first to limit processing
    sanitized = response_text[:max_length]

    # Remove API key patterns (lin_api_...)
    sanitized = re.sub(r'lin_api_[A-Za-z0-9_-]+', '[REDACTED]', sanitized)

    # Remove bearer tokens
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_-]+', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)

    # Remove authorization headers
    sanitized = re.sub(r'"authorization":\s*"[^"]*"', '"authorization": "[REDACTED]"', sanitized, flags=re.IGNORECASE)

    if len(response_text) > max_length:
        sanitized += '... [truncated]'

    return sanitized
```

**Why this pattern:**
- Prevents API key exposure in logs/database
- Truncates large responses (GraphQL errors can be verbose)
- Uses regex patterns for common credential formats

### Anti-Patterns to Avoid
- **Don't use Pydantic for simple dataclasses:** Adds unnecessary dependency when stdlib dataclasses suffice
- **Don't make API calls without config checks:** Validate configuration presence before attempting authentication
- **Don't expose raw error responses:** Always sanitize before including in VerificationCheck
- **Don't use async health checks in Django:** Synchronous checks avoid async/timeout deadlock issues
- **Don't persist health check results:** Use dataclasses (transient), not models (persisted)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timestamp generation | Manual datetime.now() | field(default_factory=func) | Prevents shared timestamps across instances |
| HTTP exception handling | Custom exception parsing | requests.HTTPError with response attribute | Captures status code, response body, and request context |
| ISO 8601 timestamps | String formatting | datetime.isoformat() | Standard format, timezone-aware, sortable |
| API response sanitization | Manual string replacement | Regex patterns with named groups | Catches credential patterns reliably |
| GraphQL error handling | Custom error parsing | Check result['errors'] from Linear API | Linear returns errors in standard GraphQL format |

**Key insight:** Health checks are diagnostic tools, not data models. Dataclasses provide structure without persistence overhead. The pattern separates computation (check functions) from structure (dataclasses) from persistence (none needed - transient results).

## Common Pitfalls

### Pitfall 1: Shared Timestamp Across Instances
**What goes wrong:** Using `timestamp: str = datetime.utcnow().isoformat()` creates one timestamp shared by all instances
**Why it happens:** Default values are evaluated once at class definition time, not per-instance
**How to avoid:** Use `field(default_factory=_get_timestamp)` to call function per-instance
**Warning signs:** All VerificationCheck instances have identical timestamps

### Pitfall 2: Exposing API Keys in Error Responses
**What goes wrong:** GraphQL errors may include request headers with Authorization field
**Why it happens:** Error responses echo back request context for debugging
**How to avoid:** Always pass responses through sanitization function before storing
**Warning signs:** `lin_api_` patterns appear in response_body fields

### Pitfall 3: Making API Calls with Invalid Configuration
**What goes wrong:** Authentication check fails with confusing error when API key is missing
**Why it happens:** Skipping configuration validation step
**How to avoid:** Run checks in order: configuration → authentication → permissions
**Warning signs:** "401 Unauthorized" when API key is not configured at all

### Pitfall 4: Using requests.raise_for_status() Without Context
**What goes wrong:** Exception raised but response details lost
**Why it happens:** raise_for_status() raises HTTPError but you need to preserve response
**How to avoid:** Catch HTTPError and extract e.response.status_code and e.response.text
**Warning signs:** Health check shows "HTTP error occurred" without status code or details

### Pitfall 5: Async Health Checks in Django
**What goes wrong:** Timeouts or deadlocks when mixing async/sync code in Django views
**Why it happens:** Django ORM is synchronous, mixing with async HTTP clients causes issues
**How to avoid:** Use synchronous requests library (already in use), avoid httpx/aiohttp
**Warning signs:** Intermittent timeouts, "SynchronousOnlyOperation" errors

### Pitfall 6: Persisting Health Check Results
**What goes wrong:** Database fills with transient health check records
**Why it happens:** Treating diagnostic checks like test results (which are persisted)
**How to avoid:** Use dataclasses (no Django model), return from API endpoint directly
**Warning signs:** Health check models in models.py, migration files for health tables

### Pitfall 7: Not Handling GraphQL-Specific Errors
**What goes wrong:** 200 OK response but GraphQL errors present in result['errors']
**Why it happens:** GraphQL returns HTTP 200 even for query errors (not HTTP 4xx/5xx)
**How to avoid:** Check both HTTP status and result.get('errors') in LinearClient._execute_query
**Warning signs:** "successful" health check but Linear queries fail

## Code Examples

Verified patterns from official sources:

### Complete Health Check Implementation
```python
# Source: Context from existing codebase patterns (linear.py, status.py, api.py)
from dataclasses import dataclass, field
from datetime import datetime
import re
import requests

def _get_timestamp() -> str:
    """Generate ISO 8601 timestamp in UTC."""
    return datetime.utcnow().isoformat() + 'Z'

@dataclass
class VerificationCheck:
    """Individual diagnostic check result.

    Attributes:
        name: Check name (e.g., "Configuration", "Authentication")
        passed: True if check succeeded
        details: Optional success details
        error_message: Optional error description
        response_status: HTTP status code if API request made
        response_body: Sanitized response body for debugging
        timestamp: ISO 8601 timestamp of check execution
    """
    name: str
    passed: bool
    details: str | None = None
    error_message: str | None = None
    response_status: int | None = None
    response_body: str | None = None
    timestamp: str = field(default_factory=_get_timestamp)

@dataclass
class TestConnectionResult:
    """Aggregated connection test result.

    Attributes:
        success: True if all checks passed
        message: Human-readable summary
        checks: List of individual check results
        error_details: Catastrophic error details (network, timeout)
    """
    success: bool
    message: str
    checks: list[VerificationCheck] | None = None
    error_details: str | None = None

def _sanitize_response(response_text: str, max_length: int = 500) -> str:
    """Sanitize API response by removing credentials."""
    sanitized = response_text[:max_length]
    sanitized = re.sub(r'lin_api_[A-Za-z0-9_-]+', '[REDACTED]', sanitized)
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_-]+', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'"authorization":\s*"[^"]*"', '"authorization": "[REDACTED]"', sanitized, flags=re.IGNORECASE)

    if len(response_text) > max_length:
        sanitized += '... [truncated]'

    return sanitized

def test_linear_connection(api_key: str, workspace: str, team: str) -> TestConnectionResult:
    """Test Linear API connection with granular diagnostics.

    Runs three checks in sequence:
    1. Configuration: Validate settings presence
    2. Authentication: Verify API key with viewer query
    3. Permissions: Verify read access to issues

    Args:
        api_key: Linear API key (lin_api_...)
        workspace: Workspace identifier
        team: Team identifier

    Returns:
        TestConnectionResult with overall success and individual checks
    """
    checks = []

    # Check 1: Configuration
    config_check = check_configuration(api_key, workspace, team)
    checks.append(config_check)
    if not config_check.passed:
        return TestConnectionResult(
            success=False,
            message="Configuration invalid",
            checks=checks
        )

    # Check 2: Authentication (requires valid config)
    from .linear import LinearClient
    client = LinearClient(api_key)
    auth_check = check_authentication(client)
    checks.append(auth_check)
    if not auth_check.passed:
        return TestConnectionResult(
            success=False,
            message="Authentication failed",
            checks=checks
        )

    # Check 3: Permissions (requires valid auth)
    perm_check = check_permissions(client)
    checks.append(perm_check)

    success = all(c.passed for c in checks)
    message = "All checks passed" if success else "Permission check failed"

    return TestConnectionResult(
        success=success,
        message=message,
        checks=checks
    )

def check_configuration(api_key: str, workspace: str, team: str) -> VerificationCheck:
    """Validate Linear configuration presence."""
    if not api_key:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY not configured"
        )

    if not api_key.startswith('lin_api_'):
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY does not match expected format (should start with 'lin_api_')"
        )

    if not workspace:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_WORKSPACE not configured"
        )

    if not team:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_TEAM not configured"
        )

    return VerificationCheck(
        name="Configuration",
        passed=True,
        details=f"API key present, workspace: {workspace}, team: {team}"
    )

def check_authentication(client) -> VerificationCheck:
    """Verify Linear API token with viewer query."""
    try:
        result = client._execute_query("""
            query Me {
                viewer {
                    id
                    name
                    email
                }
            }
        """)

        viewer = result.get('viewer', {})
        return VerificationCheck(
            name="Authentication",
            passed=True,
            details=f"Authenticated as {viewer.get('name')} ({viewer.get('email')})",
            response_status=200
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Authentication failed",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text)
        )
    except ValueError as e:
        # GraphQL errors (from _execute_query)
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"GraphQL error: {str(e)}"
        )
    except Exception as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}: {str(e)}"
        )

def check_permissions(client) -> VerificationCheck:
    """Verify read access to issues endpoint."""
    try:
        result = client._execute_query("""
            query TestIssueAccess {
                issues(first: 1) {
                    nodes {
                        id
                    }
                }
            }
        """)

        return VerificationCheck(
            name="Permissions",
            passed=True,
            details="Read access to issues endpoint confirmed",
            response_status=200
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Insufficient permissions",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text)
        )
    except ValueError as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"GraphQL error: {str(e)}"
        )
    except Exception as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}: {str(e)}"
        )
```

### Converting Dataclass to JSON Response
```python
# Source: Existing pattern from api.py
from dataclasses import asdict
from django.http import JsonResponse

def health_check_view(request):
    """API endpoint for Linear connection health check."""
    # Get config from Django settings or environment
    api_key = getattr(settings, 'LINEAR_API_KEY', '')
    workspace = getattr(settings, 'LINEAR_WORKSPACE', '')
    team = getattr(settings, 'LINEAR_TEAM', '')

    result = test_linear_connection(api_key, workspace, team)

    # Convert dataclass to dict for JSON serialization
    return JsonResponse(asdict(result))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single pass/fail boolean | Granular checks with individual results | 2020s (modern observability) | Better debugging, specific failure identification |
| Custom data structures | Dataclasses with type hints | Python 3.7+ (2018) | IDE support, auto-generated methods, type safety |
| Manual JSON serialization | dataclasses.asdict() | Python 3.7+ (2018) | One-line conversion to JSON-serializable dict |
| datetime.now() | datetime.utcnow().isoformat() | ISO 8601 standard | Timezone clarity, lexicographic sorting |
| Stored health results | Transient dataclass responses | Recent (observability shift) | Reduces database load, real-time diagnostics |

**Deprecated/outdated:**
- **Pydantic v1:** Migrated to v2 in 2023 (breaking changes in validator syntax)
- **datetime.utcnow():** Deprecated in Python 3.12+ (use datetime.now(timezone.utc) instead)
- **requests < 2.32.4:** CVE-2024-47081 (credential exposure via netrc), update to 2.32.4+

## Open Questions

Things that couldn't be fully resolved:

1. **Linear API rate limits for health checks**
   - What we know: Linear has rate limits (not documented in public docs)
   - What's unclear: Specific limits, whether viewer query counts against quota
   - Recommendation: Implement caching (e.g., cache health check result for 5 minutes)

2. **Team/workspace configuration requirements**
   - What we know: Linear API supports team and workspace filtering
   - What's unclear: Whether health check needs to validate specific team/workspace access
   - Recommendation: Include team/workspace in configuration check, don't make API calls to validate (just check presence)

3. **Sentry PR #35544 reference pattern**
   - What we know: Context mentioned this as reference but PR not found/different topic
   - What's unclear: Whether there's a specific Sentry pattern to follow
   - Recommendation: Use provided dataclass structure from context (matches industry patterns found in research)

## Sources

### Primary (HIGH confidence)
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) - Official stdlib docs for dataclass patterns
- [Linear GraphQL API documentation](https://linear.app/developers/graphql) - Official Linear API authentication and query patterns
- [Python datetime documentation](https://docs.python.org/3/library/datetime.html) - ISO 8601 timestamp handling
- [requests documentation](https://requests.readthedocs.io/en/latest/_modules/requests/exceptions/) - Exception handling patterns
- Context from existing codebase (linear.py, status.py, api.py, models.py) - Established patterns in this project

### Secondary (MEDIUM confidence)
- [Django health check patterns](https://django-health-check.readthedocs.io/en/latest/) - Django-specific health check architecture
- [Apollo GraphQL health checks](https://www.apollographql.com/docs/apollo-server/monitoring/health-checks) - GraphQL health check best practices
- [Python dataclass field default_factory pattern](https://www.pythonmorsels.com/customizing-dataclass-fields/) - Field factory patterns
- [API Security Best Practices 2026](https://dev.to/alixd/api-key-security-best-practices-for-2026-1n5d) - Credential sanitization patterns
- [GraphQL authorization patterns](https://www.apollographql.com/docs/apollo-server/security/authentication) - Authentication context patterns

### Tertiary (LOW confidence)
- [Dataclass vs Pydantic comparison](https://medium.com/@nishthakukreti.01/pydantic-vs-dataclass-640ed78a5f7c) - WebSearch only, community opinion
- [ISO 8601 best practices](https://pynative.com/python-iso-8601-datetime/) - Tutorial site, not official

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All stdlib except requests (already in use)
- Architecture: HIGH - Based on existing codebase patterns and official docs
- Pitfalls: HIGH - Common patterns from Python/Django experience and official docs warnings

**Research date:** 2026-01-21
**Valid until:** 2026-02-21 (30 days - stable technologies, stdlib-based)
