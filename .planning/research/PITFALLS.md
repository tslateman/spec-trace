# Domain Pitfalls: Integration Health Checks

**Domain:** Adding health check features to existing Django application
**Context:** SpecTrace integration health monitoring (Linear GraphQL, SLO REST APIs, CI/CD webhooks)
**Researched:** 2026-01-21
**Confidence:** HIGH (verified with official sources and current 2025-2026 documentation)

## Executive Summary

Adding integration health checks to an existing Django application introduces specific failure modes that differ from greenfield health check implementations. The primary risks cluster around: **rate limiting external APIs**, **Django async/timeout deadlocks**, **stale cached results**, **database connection pool exhaustion**, **security exposure**, and **cascading failures**. Many of these issues are invisible until production load or external API behavior changes trigger them.

---

## Critical Pitfalls

Mistakes that cause rewrites, system outages, or major architectural changes.

### Pitfall 1: Polling Third-Party APIs Without Rate Limit Awareness

**What goes wrong:**
Health checks that poll external APIs (Linear, SLO platforms) can exhaust rate limits, causing the integration to fail for real user requests. Linear's GraphQL API has strict limits: 5,000 requests/hour with API key, 250,000 complexity points/hour, and 10,000 point max per query. Health checks that run every 30 seconds would consume 60 requests/hour per check endpoint—multiplied by development, staging, and production environments, this quickly exhausts quotas.

**Why it happens:**
Health check literature recommends frequent checks (30-60 second intervals), but this advice assumes unlimited API access. Teams implement naive polling without considering third-party rate limits or cost implications (some APIs charge per call).

**Consequences:**
- Real user operations fail with rate limit errors while health checks report "healthy"
- Integration becomes unusable during business hours when usage peaks
- Emergency debugging under time pressure to add rate limiting retroactively
- Potential API key suspension for repeated violations

**Prevention:**
1. **Cache health check results** with TTL (5-15 minutes) instead of live polling
2. **Use webhook push model** where possible—Linear explicitly recommends webhooks over polling
3. **Implement request budgeting**: Track remaining quota from API response headers (Linear returns `X-RateLimit-Remaining`, `X-RateLimit-Limit`, `X-RateLimit-Reset`)
4. **Separate "connection test" from "status monitoring"**: Connection test (lightweight introspection query) runs frequently, full status checks run infrequently
5. **Monitor rate limit consumption** as a health metric itself

**Detection warning signs:**
- `RATELIMITED` error codes in API responses (Linear uses 400 status with error code)
- Health checks pass but integration features fail
- Time-of-day correlation with failures (peaks during business hours)
- Multiple environments sharing same API key hitting limits faster

**Phase to address:** Phase 1 (Architecture)—must be designed in from the start, difficult to retrofit

**Sources:**
- [Linear API Rate Limiting](https://developers.linear.app/docs/graphql/working-with-the-graphql-api/rate-limiting) - LINEAR_HIGH
- [Rate Limiting Best Practices](https://api7.ai/blog/tips-for-health-check-best-practices) - MEDIUM
- [Third-party API Rate Limiting](https://www.zigpoll.com/content/what-are-the-best-practices-for-handling-api-rate-limiting-when-integrating-thirdparty-services-in-a-web-application) - MEDIUM

---

### Pitfall 2: Django Async/Timeout Deadlocks in Health Check Endpoints

**What goes wrong:**
Django 4.2+ with asgiref 3.8+ experiences main thread deadlocks when HTTP requests timeout (60s nginx timeout is common). If a health check endpoint uses `async_to_sync()` or `sync_to_async()` and the external API call times out, the entire Django/Daphne process can deadlock, blocking ALL subsequent requests—not just the timed-out health check. This turns a single slow API response into a complete system outage.

**Why it happens:**
Django's async bridge (`asgiref`) changed thread management in 3.8.0+, introducing deadlock conditions when timeouts interact with thread-sensitive contexts. Health checks often trigger this by wrapping synchronous API calls (Linear GraphQL, REST SLO platforms) with async wrappers to avoid blocking.

**Consequences:**
- Complete system unresponsiveness requiring process restart
- Cascading failures as load balancers detect unhealthy instances and route more traffic to fewer nodes
- Health checks themselves become the primary cause of downtime
- 10-15 second delay between timeout and deadlock makes debugging difficult (symptoms appear unrelated)

**Prevention:**
1. **Set aggressive connection timeouts** on ALL external API calls (2-5 seconds max for health checks)
2. **Avoid `async_to_sync()` in views** that call external APIs—use httpx/aiohttp with native async instead of requests
3. **Use circuit breaker pattern**: After N consecutive failures, stop calling external API for cooldown period
4. **Test timeout behavior explicitly**: `pytest-timeout` with forced delays to verify graceful handling
5. **Monitor thread pool exhaustion**: Track active threads and queue depth

**Example vulnerable code pattern (current SpecTrace code):**
```python
# requirements/linear.py - uses requests.Session (synchronous)
response = self.session.post(self.API_URL, json=payload)
# If this times out in an async context → deadlock risk
```

**Detection warning signs:**
- Complete system hang after 60+ seconds of slow API responses
- `sync_to_async` or `async_to_sync` in stack traces before hang
- Health check timeout correlation with system-wide unresponsiveness
- Django debug toolbar showing deadlock when concurrent async operations run

**Phase to address:** Phase 1 (Architecture)—must choose async-native HTTP client from start

**Sources:**
- [Django Async Deadlock Issues](https://forum.djangoproject.com/t/django-4-2-16-daphne-4-1-2-http-requests-timeout-result-main-thread-deadlock/38835) - HIGH (2025)
- [sync_to_async Deadlocks](https://github.com/django/asgiref/issues/348) - HIGH
- [Django Async Best Practices](https://docs.djangoproject.com/en/5.0/_modules/asgiref/sync/) - HIGH

---

### Pitfall 3: Health Check Endpoint Exposing Sensitive Integration Details

**What goes wrong:**
Health check responses that include API keys, internal URLs, database connection strings, error messages with stack traces, or detailed integration configuration become reconnaissance tools for attackers. Even seemingly innocent details like "Linear API: team=ACME, workspace_id=abc123" leak organizational structure.

**Why it happens:**
Developers prioritize debuggability and include rich error context in health check responses. Default Django error pages (when DEBUG=True) expose full tracebacks. API endpoints at `/api/health` or `/status` are often exempt from authentication because monitoring systems need unauthenticated access.

**Consequences:**
- Information disclosure enables targeted attacks
- Compliance violations (SOC2, HIPAA) if PII/PHI in error messages
- Attackers map internal architecture and identify vulnerable components
- API keys leaked in logs/monitoring systems that store health check responses

**Prevention:**
1. **Return minimal response structure**: `{"status": "healthy/degraded/unhealthy", "timestamp": "..."}` only
2. **Separate internal vs. external health endpoints**: `/health` (public, minimal) vs. `/admin/health/detailed` (authenticated, verbose)
3. **Never include in responses**: API keys, tokens, passwords, internal IPs, database names, user counts, exact version numbers
4. **Sanitize error messages**: Generic "integration error" not "LinearClient auth failed: invalid token lin_api_xyz"
5. **Use authentication even for basic health checks** or restrict by IP allowlist
6. **HTTPS only**, no exceptions—health checks over HTTP expose sensitive headers

**Example vulnerable pattern:**
```python
# DON'T DO THIS
return JsonResponse({
    "linear": {
        "status": "failed",
        "error": str(e),  # Exposes "Authorization failed for key lin_api_..."
        "api_url": LINEAR_API_URL,
        "last_query": query_string
    }
})
```

**Detection warning signs:**
- Health check endpoints return different status codes based on auth state (leaks valid usernames)
- Error messages in responses contain tokens, keys, or internal paths
- Monitoring dashboards display API keys in health check history
- No authentication required to access health status

**Phase to address:** Phase 2 (Implementation)—design response format in Phase 1, enforce sanitization in Phase 2

**Sources:**
- [Azure Health Endpoint Security](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring) - HIGH
- [Spring Boot Endpoint Security](https://docs.spring.io/spring-boot/reference/actuator/endpoints.html) - HIGH
- [API Health Check Security](https://api7.ai/blog/tips-for-health-check-best-practices) - MEDIUM

---

### Pitfall 4: Database Connection Pool Exhaustion from Health Checks

**What goes wrong:**
Health check endpoints query the database to verify connectivity, but under load or during incidents, these checks can exhaust the connection pool, preventing real application queries from executing. A paradox: the health check trying to detect database issues *causes* database issues by consuming the last available connections.

**Why it happens:**
Each health check request opens a database connection (Django ORM requires a connection for any query). With frequent checks (30-60s), multiple monitoring sources (load balancer, APM, external monitors), and multiple application instances, connection consumption adds up. During incidents (slow queries, connection leaks), health checks compete with real traffic for scarce connections.

**Consequences:**
- Application reports 500 errors while health check reports "database healthy"
- Cascading failures as health check itself becomes a DDoS attack on the database
- False positives: health check has dedicated connection that succeeds while application pool exhausted
- Emergency mitigation requires disabling health checks, leaving system blind during incident

**Prevention:**
1. **Use connection pooling with reserve capacity**: If max pool = 100, reserve 10 for health checks via separate pool
2. **Don't run DB queries in health checks** unless absolutely necessary—check `/health` without DB, `/health/detailed` with DB (less frequent)
3. **Implement health check connection timeout** (2-5 seconds max, not default 30s)
4. **Use Django connection health check**: `connection.ensure_connection()` instead of full query
5. **Monitor connection pool metrics**: Active, idle, waiting queue depth—alert before exhaustion
6. **Fail fast**: Circuit breaker after 3 consecutive DB check failures, stop trying for 60s

**Current SpecTrace risk:**
```python
# api.py line 277 - get_requirement_status runs queries
requirement = Requirement.objects.get(external_id=external_id)
test_count = requirement.test_results.count()  # Multiple DB queries
# If load balancer polls this frequently → connection pressure
```

**Detection warning signs:**
- Application 500 errors with "connection pool exhausted" while health returns 200
- Health check response time increases during high traffic
- Database connection count spikes correlate with health check intervals
- Connection timeout errors only during peak load, not off-hours

**Phase to address:** Phase 1 (Architecture)—connection pooling strategy must be designed upfront

**Sources:**
- [Connection Pool Exhaustion](https://howtech.substack.com/p/connection-pool-exhaustion-the-silent) - HIGH (2025)
- [Health Check Connection Leaks](https://github.com/rundeck/rundeck/issues/2347) - HIGH
- [Database Health Check Issues](https://medium.com/@shahharsh172/database-connection-pool-optimization-from-500-errors-to-99-9-uptime-9deb985f5164) - MEDIUM

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or require significant rework.

### Pitfall 5: Cascading Failures from Checking Downstream Health

**What goes wrong:**
Health check endpoint that queries the health of downstream integrations (Linear, SLO platform) marks the entire application as unhealthy when a single integration fails, even if that integration isn't critical. Load balancers remove healthy instances from rotation, compounding the problem. A temporary Linear API slowdown triggers a full SpecTrace outage.

**Why it happens:**
Simplistic health check design: "if any dependency fails, return 503." This follows the principle "fail if something is broken," but ignores that different dependencies have different criticality. Linear sync being down shouldn't make the entire dashboard inaccessible.

**Prevention:**
1. **Separate liveness vs. readiness checks**: Liveness = process alive, readiness = critical dependencies ready
2. **Tiered health status**: `healthy` (all good), `degraded` (non-critical failure), `unhealthy` (critical failure)
3. **Don't check downstream health in liveness probe**—only check process health (e.g., can we respond to HTTP?)
4. **Cache last successful state**: If Linear fails, show last-known-good data for 15 minutes before marking degraded
5. **Circuit breaker pattern**: After N failures, stop checking dependency for cooldown period, return cached state

**Response format example:**
```json
{
  "status": "degraded",
  "components": {
    "database": {"status": "healthy", "latency_ms": 5},
    "linear_api": {"status": "degraded", "error": "rate limit exceeded", "cached_until": "2026-01-21T10:45:00Z"},
    "slo_platform": {"status": "healthy", "latency_ms": 120}
  }
}
```

**Detection warning signs:**
- All application instances marked unhealthy simultaneously when external API slows
- Health check returns 503 but application features still work
- Outages correlate with third-party service status pages

**Phase to address:** Phase 2 (Implementation)—requires careful status aggregation logic

**Sources:**
- [Cascading Health Check Failures](https://thinhdanggroup.github.io/health-check-api/) - MEDIUM
- [Health Check Anti-patterns](https://microservices.io/patterns/observability/health-check-api.html) - MEDIUM

---

### Pitfall 6: GraphQL Introspection Query Performance Impact

**What goes wrong:**
Using GraphQL introspection queries (e.g., `query { __typename }`) as a "lightweight" health check actually performs full schema traversal, consuming significant CPU and memory. Under high frequency (every 30s from multiple sources), this creates noticeable performance impact and can trigger rate limit complexity penalties.

**Why it happens:**
Common recommendation for GraphQL health checks is introspection query because it's "guaranteed to work." But introspection requires the server to traverse the entire schema and gather metadata—far from lightweight. Linear's complexity-based rate limiting counts introspection queries against the 250,000 point/hour limit.

**Prevention:**
1. **Use a minimal query instead**: `query { viewer { id } }` (just fetch authenticated user ID, not full schema)
2. **Don't use introspection in production** (often disabled for security anyway)
3. **Cache introspection results locally** if schema validation is needed, re-fetch only on deployment
4. **Consider HTTP HEAD request** to GraphQL endpoint instead—verifies connectivity without query execution
5. **Monitor query complexity**: Track points consumed per health check, ensure it's under 10 points

**Example lightweight alternative:**
```graphql
# Instead of introspection (expensive)
query HealthCheck {
  __typename
}

# Use minimal authenticated query (cheap)
query HealthCheck {
  viewer {
    id
  }
}
```

**Detection warning signs:**
- GraphQL server CPU spikes correlate with health check intervals
- Rate limit errors during normal operations
- Slow response times from health checks that "should be instant"

**Phase to address:** Phase 2 (Implementation)—query design choice

**Sources:**
- [GraphQL Introspection Performance](https://graphql.org/learn/introspection/) - HIGH
- [GraphQL Health Checks](https://www.apollographql.com/docs/apollo-server/monitoring/health-checks) - HIGH
- [Introspection Security Tradeoffs](https://escape.tech/blog/should-i-disable-introspection-in-graphql/) - MEDIUM

---

### Pitfall 7: Stale Cached Health Status Misleading Users

**What goes wrong:**
Caching health check results (to avoid rate limits) without clear cache expiry indication causes users to trust stale status. "Linear integration: Healthy (last checked 3 hours ago)" is dangerously misleading—it could have failed 2 hours 59 minutes ago.

**Why it happens:**
Caching is necessary to prevent rate limiting (see Pitfall 1), but teams forget to communicate cache freshness. UI shows cached status as if it were current. Debugging sessions waste time because displayed status doesn't reflect reality.

**Prevention:**
1. **Always show last checked timestamp** in UI: "Healthy (checked 2 minutes ago)"
2. **Visual indicator for stale data**: Yellow badge after 5 minutes, red after 15 minutes
3. **Explicit "Refresh" button** to force immediate health check (with rate limit warning)
4. **Include cache metadata in API responses**:
   ```json
   {
     "status": "healthy",
     "checked_at": "2026-01-21T10:30:00Z",
     "cached": true,
     "cache_expires_at": "2026-01-21T10:35:00Z"
   }
   ```
5. **Asynchronous refresh**: Background job runs health checks on schedule, updates cache, UI polls cache (never triggers direct check)

**Detection warning signs:**
- Users report integration failures but dashboard shows healthy
- Time gap between failure reports and status change
- Debugging based on stale status wastes time

**Phase to address:** Phase 3 (Dashboard)—UI design and cache transparency

**Sources:**
- [Cache Invalidation Best Practices](https://redis.io/glossary/cache-invalidation/) - MEDIUM
- [Health Check Caching](https://github.com/dotnet-architecture/HealthChecks/issues/12) - MEDIUM
- [Stale Data Prevention](https://www.fastly.com/documentation/guides/concepts/healthcheck/) - MEDIUM

---

### Pitfall 8: Webhook Endpoint Missing Authentication

**What goes wrong:**
CI/CD webhook endpoints (`@csrf_exempt` required) accept test results from any source, enabling attackers to inject false "all tests passing" results or pollute the database with garbage data. Current SpecTrace code has `@csrf_exempt` on `/api/slo/status/` and `/api/validation/result/` without authentication.

**Why it happens:**
Webhook receivers must disable CSRF protection (webhooks don't have CSRF tokens), leading developers to skip authentication entirely. Pressure to "just make it work" during integration testing means auth is deferred and forgotten.

**Consequences:**
- False positive: Dashboard shows "all tests passing" when they're failing (injected fake results)
- Data pollution requiring manual cleanup
- Compliance violations: Audit trails compromised by unauthenticated writes
- Reputation damage if security audit discovers public write endpoints

**Prevention:**
1. **HMAC signature verification**: Webhook sender signs payload with shared secret, receiver verifies
   ```python
   import hmac
   def verify_webhook(request, secret):
       signature = request.headers.get('X-Webhook-Signature')
       payload = request.body
       expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
       return hmac.compare_digest(signature, expected)
   ```
2. **API key in header**: `Authorization: Bearer <token>` required for all webhook endpoints
3. **IP allowlist**: Only accept webhooks from known CI/CD runner IPs (less reliable, IPs change)
4. **Timestamp validation**: Reject requests with timestamps >5 minutes old (prevents replay attacks)
5. **Rate limiting**: Per-source rate limits prevent abuse even if auth compromised

**Current SpecTrace vulnerable pattern:**
```python
# api.py lines 22-23, 122-123
@csrf_exempt
@require_http_methods(["POST"])
def update_slo_status(request):  # No authentication check
```

**Detection warning signs:**
- Unexpected data appearing in database
- Status changes not correlating with known events
- Security scanning tools flag unauthenticated write endpoints

**Phase to address:** Phase 2 (Implementation)—add before public deployment

**Sources:**
- [Django Webhook Security](https://anymail.dev/en/stable/tips/securing_webhooks/) - HIGH
- [Webhook Authentication Strategies](https://www.hooklistener.com/learn/webhook-authentication-strategies) - MEDIUM (2025)
- [HMAC Webhook Verification](https://dev.to/aakas/webhooks-in-django-a-comprehensive-guide-44jp) - MEDIUM

---

## Minor Pitfalls

Mistakes that cause annoyance or require iteration, but are relatively easy to fix.

### Pitfall 9: False Positive Alerts from Overly Sensitive Thresholds

**What goes wrong:**
Health checks configured with hair-trigger sensitivity (e.g., "fail if response time >100ms" or "alert after 1 failed check") flood on-call engineers with false positive alerts, leading to alert fatigue and ignored genuine incidents.

**Prevention:**
1. **Baseline normal behavior first**: Measure typical response times before setting thresholds
2. **Use consecutive failure counts**: Alert after 3-5 consecutive failures, not 1
3. **Percentage-based thresholds**: Alert if >10% of checks fail in 5-minute window
4. **Different thresholds for different times**: Higher tolerance during known maintenance windows
5. **Gradual escalation**: Warning after 2 failures, page after 5 failures

**Phase to address:** Phase 4 (Monitoring)—after initial deployment, tune based on operational data

**Sources:**
- [False Positive Prevention](https://panther.com/blog/identifying-and-mitigating-false-positive-alerts) - MEDIUM
- [Alert Threshold Tuning](https://betterstack.com/community/guides/monitoring/health-checks/) - MEDIUM

---

### Pitfall 10: Mixing Configuration Scopes (ALLOWED_HOSTS for Health Checks)

**What goes wrong:**
Load balancer health checks from private IPs fail because Django's `ALLOWED_HOSTS` doesn't include them. Adding private IPs to `ALLOWED_HOSTS` works until instance reboot changes the IP, breaking health checks again.

**Prevention:**
1. **Use DNS names in ALLOWED_HOSTS** instead of IPs: `['spectrace.internal', '*.compute.amazonaws.com']`
2. **Health check endpoint bypass**: Middleware that skips `ALLOWED_HOSTS` check for `/health` path only
3. **Environment variable for dynamic IPs**: `ALLOWED_HOSTS = ['localhost'] + os.environ.get('HEALTH_CHECK_IPS', '').split(',')`
4. **Container orchestration health checks**: Use HTTP from within cluster, not external load balancer

**Phase to address:** Phase 2 (Implementation)—deployment configuration

**Sources:**
- [Django ALLOWED_HOSTS for Health Checks](https://www.ianlewis.org/en/kubernetes-health-checks-django) - MEDIUM
- [Health Check Configuration Issues](http://chongkim.org/programming/2018/04/05/health-check-on-a-django-server.html) - LOW

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation Strategy | Priority |
|-------------|---------------|---------------------|----------|
| **Phase 1: Architecture** | Rate limiting external APIs (P1) | Design caching and request budgeting into VerificationCheck pattern | CRITICAL |
| | Async/timeout deadlocks (P2) | Choose async-native HTTP client (httpx), avoid requests + async_to_sync | CRITICAL |
| | Database connection exhaustion (P4) | Plan separate connection pool or connection-less health checks | HIGH |
| **Phase 2: API Endpoints** | Security exposure (P3) | Design minimal response format, sanitize errors | CRITICAL |
| | Webhook authentication (P8) | Implement HMAC or API key auth before public deployment | HIGH |
| | GraphQL query design (P6) | Use minimal queries, not introspection | MEDIUM |
| **Phase 3: Dashboard** | Stale cache indication (P7) | Show timestamps, cache expiry, refresh button | MEDIUM |
| | Cascading failure presentation (P5) | Implement degraded status tier, show component breakdown | MEDIUM |
| **Phase 4: Monitoring** | False positive alerts (P9) | Use consecutive failure thresholds, baseline before alerting | LOW |

---

## Testing Checklist

Before shipping integration health checks, validate these scenarios:

**Rate Limiting:**
- [ ] Health check respects API rate limits (Linear 5,000/hour, complexity 250,000/hour)
- [ ] Cached results served when quota exhausted
- [ ] Rate limit errors logged but don't crash health check

**Timeout Handling:**
- [ ] External API timeout (force 60s delay) doesn't deadlock Django process
- [ ] Health check returns error state, not hangs indefinitely
- [ ] Concurrent health checks don't block each other

**Security:**
- [ ] Health check response contains no API keys, tokens, or internal URLs
- [ ] Error messages sanitized (generic messages, not full tracebacks)
- [ ] Webhook endpoints require authentication (HMAC or API key)
- [ ] All health endpoints use HTTPS only

**Database:**
- [ ] Health check under simulated load doesn't exhaust connection pool
- [ ] Connection timeout set (2-5 seconds)
- [ ] Health check failure doesn't prevent application queries

**Cascading Failures:**
- [ ] Single integration failure doesn't mark entire app unhealthy
- [ ] Degraded status tier supported
- [ ] Liveness probe independent of integration health

**Cache Transparency:**
- [ ] UI shows "last checked" timestamp
- [ ] Stale cache indicated visually
- [ ] Manual refresh available with rate limit warning

---

## Confidence Assessment

| Pitfall | Confidence | Reasoning |
|---------|-----------|-----------|
| P1: Rate limiting | HIGH | Linear official docs, multiple 2025-2026 sources confirm limits |
| P2: Async deadlocks | HIGH | Django forum reports from 2025 with specific version numbers |
| P3: Security exposure | HIGH | Microsoft Azure, Spring Boot official security guidance |
| P4: Connection exhaustion | HIGH | Multiple case studies, GitHub issues with examples |
| P5: Cascading failures | MEDIUM | Best practices from multiple sources, not SpecTrace-specific |
| P6: GraphQL introspection | MEDIUM | Official GraphQL docs, Apollo guidance |
| P7: Stale cache | MEDIUM | Fastly official docs, general caching principles |
| P8: Webhook auth | HIGH | Django webhook security guides, 2025 best practices |
| P9: False positives | MEDIUM | General monitoring best practices, multiple sources agree |
| P10: ALLOWED_HOSTS | LOW | Django-specific but well-documented, older issue |

---

## Research Methodology

**Sources Used:**
- **Context7:** Not available for Django health check libraries
- **Official Documentation:** Django 5.2, Linear API, Microsoft Azure, Spring Boot
- **WebSearch:** 2025-2026 articles, blog posts, GitHub issues, forum discussions
- **Verification:** Cross-referenced multiple sources for critical claims (P1-P4, P8)

**Verification Status:**
- Critical pitfalls (P1-P4): Verified with official docs or recent (2025) issue reports
- Moderate pitfalls (P5-P8): Verified with multiple credible sources
- Minor pitfalls (P9-P10): Standard best practices, widely documented

**What wasn't found:**
- SpecTrace-specific prior art (new application, no existing community)
- Long-term production experience (recent tech stack: Django 5.2, 2026 deployment)
- Comprehensive integration health check framework for Django (most solutions are generic health checks)

---

## Recommended Reading Order for Roadmap Planning

1. **Start with P1 (rate limiting)** - Most likely to cause immediate production issues
2. **Then P2 (async deadlocks)** - Can cause complete system outage
3. **Then P8 (webhook auth)** - Security vulnerability, must fix before public deployment
4. **Then P3 (security exposure)** - Related to P8, similar security concerns
5. **Then P4 (connection pool)** - Performance/scalability issue
6. **Others as needed** - P5-P7 improve UX/reliability, P9-P10 operational quality

This ordering prioritizes issues that: 1) cause outages, 2) create security vulnerabilities, 3) affect performance, 4) impact user experience.
