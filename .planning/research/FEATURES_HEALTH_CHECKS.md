# Feature Landscape: Integration Health Checks

**Domain:** Integration health monitoring and connection testing
**Researched:** 2026-01-21
**Context:** Subsequent milestone for SpecTrace - adding health checks to existing Linear/SLO integrations

## Executive Summary

Integration health checks are a standard observability pattern for monitoring third-party API connectivity, configuration validity, and diagnostic status. Based on research of current practices (2026), health checking follows well-established conventions around HTTP status codes (200 for healthy, 503 for unhealthy), structured check results with individual verification steps, and graduated response patterns (liveness, readiness, health).

SpecTrace's Canary-derived VerificationCheck pattern aligns with industry standards while adding granular diagnostic capabilities (response_status, response_body, error_message fields). The key differentiation opportunity lies in integration-specific diagnostics and proactive dashboard visibility rather than basic connectivity testing.

## Table Stakes

Features users expect from integration health monitoring. Missing these = incomplete feature.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Configuration validation** | First check before attempting connection - "is API key present?" | Low | Must happen before network calls to provide early exit |
| **Connection test endpoint** | Standard pattern - `/health` or `/api/integrations/health/` | Low | HTTP POST with integration name, returns structured result |
| **HTTP status code standards** | 200 for success, 4xx/5xx for failures | Low | Follows [IETF health check draft](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check-06) |
| **Individual check granularity** | Multiple named checks per integration (config → auth → connectivity) | Medium | Pattern from [AWS health check implementation](https://aws.amazon.com/builders-library/implementing-health-checks/) |
| **Error message capture** | When check fails, capture specific error (timeout, 401, GraphQL error) | Low | Critical for debugging - users need to know WHY it failed |
| **Response status tracking** | Log HTTP status codes for failed requests | Low | Standard diagnostic field in all health check systems |
| **Timestamp per check** | ISO 8601 timestamp for each verification step | Low | Enables "last checked" UI and troubleshooting timing issues |
| **Success/failure aggregation** | Overall result = all checks passed | Low | Top-level `success: boolean` field |
| **Timeout handling** | Connection attempts must timeout (10s typical) | Low | Prevents hung requests; [retry best practices](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry) recommend 10s |
| **Idempotent checks** | Running health check doesn't mutate state | Low | Checks must be read-only operations |

## Differentiators

Features that set SpecTrace apart. Not expected, but valuable for power users.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Response body capture** | Truncated response body (500 chars) for debugging GraphQL errors | Low | Canary pattern - helps debug malformed queries |
| **Multi-check early exit** | Skip connection test if config check fails | Low | Prevents misleading "connection failed" when real issue is missing API key |
| **Integration-specific diagnostics** | Linear: shows connected user name; SLO: shows platform version | Medium | Goes beyond pass/fail to show contextual info |
| **Dashboard health indicators** | Admin dashboard shows integration status without manual test | Medium | Proactive visibility - users see problems before they encounter them |
| **Batch health endpoint** | `GET /api/integrations/health/all/` returns all integrations at once | Low | Reduces API calls for monitoring dashboards |
| **Detailed check history** | Each check's individual pass/fail state, not just final result | Low | Users can see "config passed but auth failed" - valuable for troubleshooting |
| **GraphQL-aware error parsing** | Detect `errors` key in GraphQL response even with 200 status | Medium | Linear API returns 200 with errors array - must parse payload |
| **Verification method validation** | Test that Linear labels include verify:test or verify:inapp | Medium | Integration-specific - validates that requirements have proper metadata |
| **Cached status display** | Dashboard caches last health check result (avoid slow page loads) | Medium | [Azure health endpoint pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring) - periodic check + cache |
| **Non-blocking UI tests** | Dashboard "Test Connection" button triggers async check | Medium | Prevents 10s page hang during timeout scenarios |

## Anti-Features

Features to explicitly NOT build. Common mistakes in health check implementations.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Deep dependency checks in liveness** | Failing health check if ONE dependency is down increases blast radius | Check critical path only; use separate readiness check for dependencies ([AWS pattern](https://aws.amazon.com/builders-library/implementing-health-checks/)) |
| **Synchronous health checks in request path** | Health check that blocks page render for 10s during timeout | Cache health status, refresh async ([health check anti-patterns](https://seifrajhi.github.io/blog/Kubernetes-anti-patterns/)) |
| **Mutating operations in health checks** | Creating test data, writing to database during health check | Health checks must be read-only and idempotent |
| **Retrying failed health checks automatically** | Health check endpoint that retries 3x on failure = 30s response time | Single attempt per check; let monitoring system handle retry cadence ([retry best practices](https://harish-bhattbhatt.medium.com/best-practices-for-retry-pattern-f29d47cd5117)) |
| **Exposing full response bodies** | Leaking sensitive data (API keys, tokens) in diagnostic responses | Truncate to 500 chars and redact sensitive patterns |
| **401/403 as overall healthy** | Returning 200 OK when auth fails because "the endpoint is up" | Auth failure = unhealthy integration; use 503 or failed success field |
| **Silent timeout failures** | Connection timeout that doesn't populate error_message | Always capture timeout exceptions as errors with context |
| **Testing non-critical integrations in critical path** | Blocking app startup because optional Slack integration is down | Separate critical (required for core function) from optional integrations |
| **Health checks without authentication** | Public `/health` endpoint that tests all API keys | Require auth for detailed checks or rate-limit public endpoint |
| **Storing API keys in health check responses** | Returning full config including secrets in diagnostic output | Never echo secrets; return "configured: true" instead of actual values |

## Feature Dependencies

```
Configuration Check
  ├─ enables → Authentication Check
  │              ├─ enables → Connectivity Check
  │              └─ enables → Integration-Specific Checks
  │
  └─ early exit if failed (prevents misleading errors)

Dashboard Display
  ├─ requires → Cached Status (avoid slow page loads)
  └─ requires → Individual Check Results (show specific failure)

Batch Health Endpoint
  └─ requires → Individual Integration Checkers

Integration-Specific Diagnostics
  ├─ Linear: requires → GraphQL viewer query parsing
  ├─ SLO: requires → Platform health endpoint access
  └─ CI/CD: requires → JUnit XML path validation
```

## MVP Recommendation

For MVP integration health checks in SpecTrace, prioritize:

### Must Have (MVP Core)
1. **VerificationCheck dataclass** - name, passed, details, error_message, timestamp
2. **TestConnectionResult dataclass** - success, message, checks array
3. **LinearHealthChecker.test_connection()** - config check → auth check (viewer query)
4. **API endpoint** - POST `/api/integrations/health/` with integration parameter
5. **Error message capture** - Timeout, HTTP status, GraphQL errors
6. **Response status tracking** - Log status codes for failed requests
7. **Early exit on config failure** - Skip connection if API key missing

### Should Have (MVP Nice-to-Have)
8. **Response body truncation** - First 500 chars for debugging
9. **Integration-specific context** - Show connected Linear user name
10. **Batch endpoint** - GET `/api/integrations/health/all/`

### Defer to Post-MVP
- **Dashboard integration health indicators** - Cached status display (complexity: requires async refresh)
- **Admin UI "Test Connection" buttons** - Non-blocking async tests (complexity: frontend work)
- **SLO platform health checker** - Depends on SLO integration implementation
- **CI/CD health checker** - Depends on webhook/import integration architecture
- **Historical health tracking** - Store check results in database (complexity: schema design)
- **Scheduled health checks** - Django-Q periodic tasks (complexity: requires task queue setup)
- **Health check alerting** - Notify when integrations become unhealthy (complexity: notification system)
- **Webhook signature validation** - Test incoming webhook authentication (complexity: crypto operations)

## Complexity Notes

### Low Complexity (1-2 hours)
- Configuration checks (boolean "is key present?")
- HTTP status code mapping (standard conventions)
- Timestamp generation (stdlib datetime)
- Error message capture (try/except string conversion)
- Dataclass to_dict() serialization

### Medium Complexity (3-6 hours)
- GraphQL-aware error parsing (detect errors in 200 response)
- Integration-specific diagnostics (parse user info from response)
- Dashboard health indicators (template changes + view updates)
- Batch health endpoint (iterate checkers, aggregate results)
- Cached status display (caching strategy + invalidation)

### High Complexity (1+ days)
- Non-blocking async UI tests (frontend + backend coordination)
- Historical health tracking (model design + migrations + retention)
- Scheduled health checks (task queue setup + job configuration)
- Health check alerting (notification channels + routing logic)

## Existing SpecTrace Dependencies

SpecTrace already has the foundation for health checks:

| Existing Feature | How It Helps |
|------------------|--------------|
| **LinearClient API wrapper** | Add test_connection() method to existing client |
| **Django REST endpoints** | Pattern established in requirements/api.py for JSON responses |
| **Settings-based config** | LINEAR_API_KEY already in settings for checkers to validate |
| **Unfold admin dashboard** | Extension point for health indicators via dashboard_callback |
| **requests library** | Already installed for Linear GraphQL calls |

This reduces implementation risk - no new dependencies, just extending existing patterns.

## Integration-Specific Behaviors

### Linear API Health Check

**Check sequence:**
1. Config check: LINEAR_API_KEY present in settings
2. Auth check: GraphQL viewer query with API key
3. Parse response: Extract user name from viewer data

**Expected responses:**
- Success: 200 with `{data: {viewer: {name: "..."}}}` → show connected user
- Auth failure: 401 → "Invalid API key"
- GraphQL error: 200 with `{errors: [...]}` → parse error array
- Network failure: requests.RequestException → "Connection failed"

**Integration-specific features:**
- Label validation: Check if LINEAR_LABEL setting exists
- Issue count query: Optional check to verify label returns results

### SLO Platform Health Check

**Check sequence:**
1. Config check: SLO_PLATFORM_URL present in settings
2. Health endpoint: GET `{url}/health`
3. Response validation: 200 status = healthy

**Expected responses:**
- Success: 200 → "Platform is healthy"
- Unhealthy: 503 → "Platform reports unhealthy"
- Timeout: Connection timeout → "Platform unreachable"

**Integration-specific features:**
- Webhook reachability: Optional reverse check (can SLO platform reach us?)
- Version detection: Parse platform version from health response if available

### CI/CD Health Check (Future)

**Check sequence:**
1. Config check: JUNIT_XML_PATH or WEBHOOK_SECRET configured
2. Path accessibility: Can read from configured path
3. Recent results: JUnit XML files exist from recent runs

**Expected responses:**
- Success: Recent XML files found → show timestamp of latest
- Missing: No XML files → "No test results imported"
- Access denied: Permission error → "Cannot access test results"

## Standard HTTP Status Codes

Per [IETF health check draft](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check-06) and [MDN status codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status):

| Status | Meaning | Use in Health Checks |
|--------|---------|---------------------|
| **200 OK** | Success | All checks passed, integration healthy |
| **401 Unauthorized** | Auth failed | API key invalid or missing |
| **403 Forbidden** | Access denied | Valid auth but insufficient permissions |
| **408 Request Timeout** | Timeout | Connection attempt exceeded timeout (10s) |
| **429 Too Many Requests** | Rate limited | Hit API rate limit during check |
| **500 Internal Server Error** | Server error | Unexpected error during check execution |
| **503 Service Unavailable** | Unhealthy | One or more checks failed |

**SpecTrace convention:**
- Health check endpoint always returns 200 for valid requests
- Success/failure indicated in JSON `success: boolean` field
- Individual check `response_status` captures upstream API status

## Sources

### Health Check Standards & Best Practices
- [IETF Health Check Response Format (Draft)](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check-06) - Standard response structure
- [AWS Builders Library: Implementing Health Checks](https://aws.amazon.com/builders-library/implementing-health-checks/) - Best practices from AWS
- [Azure Health Endpoint Monitoring Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring) - Enterprise health check patterns
- [Microservices Health Check API Pattern](https://microservices.io/patterns/observability/health-check-api.html) - Microservices-specific patterns
- [Better Stack: Health Check Best Practices](https://betterstack.com/community/guides/monitoring/health-checks/) - Modern implementation guide
- [API7: Health Check Best Practices](https://api7.ai/blog/tips-for-health-check-best-practices) - API gateway perspective

### Connection Testing & Error Handling
- [Microsoft: Retry Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry) - Retry logic best practices
- [Best Practices for Retry Pattern](https://harish-bhattbhatt.medium.com/best-practices-for-retry-pattern-f29d47cd5117) - Exponential backoff patterns
- [API4.ai: Implementing Retry Logic](https://api4.ai/blog/best-practice-implementing-retry-logic-in-http-api-clients) - HTTP client retry patterns
- [Chainstack: Error Handling in API Requests](https://docs.chainstack.com/docs/best-practices-for-error-handling-in-api-requests) - API error handling

### Health Check Anti-Patterns
- [Kubernetes Health Check Anti-Patterns](https://seifrajhi.github.io/blog/Kubernetes-anti-patterns/) - Common mistakes in K8s
- [DZone: Overview of Health Check Patterns](https://dzone.com/articles/an-overview-of-health-check-patterns) - Patterns and anti-patterns

### Dashboard & Monitoring Patterns
- [ASP.NET Core Health Checks UI](https://github.com/Xabaril/AspNetCore.Diagnostics.HealthChecks) - Open source health check dashboard
- [StatusGator: Status Page Monitoring](https://statusgator.com/blog/status-page-monitoring/) - Third-party status aggregation
- [Uptime.com: Third-Party Status Monitoring](https://uptime.com/status-page-monitoring) - Monitoring service status pages
- [Microsoft: Health Monitoring for .NET](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/implement-resilient-applications/monitor-app-health) - .NET health monitoring patterns

### HTTP Standards
- [MDN: HTTP Response Status Codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) - Official HTTP status reference
- [Health Check Response Format for HTTP APIs](https://blog.frankel.ch/healthcheck-http-apis/) - Structured response patterns
