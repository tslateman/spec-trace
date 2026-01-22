# Milestone v3: Integration Health Checks

**Status:** SHIPPED 2026-01-22
**Phases:** 5-7
**Total Plans:** 8

## Overview

v3 adds integration health monitoring with granular diagnostic checks for Linear. The system tests configuration, authentication, and permissions, exposes results via API endpoints, and displays health status in the dashboard with manual testing capability.

## Phases

### Phase 5: Health Check Foundation

**Goal:** Core domain objects and granular diagnostic checks for Linear integration
**Depends on:** v2 complete
**Plans:** 6 plans

Plans:

- [x] PLAN-01 — VerificationCheck and TestConnectionResult dataclasses
- [x] PLAN-02 — Response sanitization function
- [x] PLAN-03 — Configuration check function
- [x] PLAN-04 — Authentication check function
- [x] PLAN-05 — Permissions check function
- [x] PLAN-06 — verify_linear_connection aggregator

**Details:**
- Requirements: HEALTH-02, HEALTH-03, HEALTH-04
- Success Criteria:
  1. VerificationCheck dataclass exists with name, passed, details, timestamp fields
  2. TestConnectionResult dataclass aggregates multiple checks
  3. Configuration check validates Linear API key, workspace, and team presence
  4. Authentication check makes actual API request to verify token validity
  5. Permissions check verifies read access to issues endpoint
  6. Failed checks include error_message and sanitized response details

### Phase 6: API Endpoints

**Goal:** REST endpoints for triggering health checks and retrieving cached status
**Depends on:** Phase 5
**Plans:** 1 plan

Plans:

- [x] PLAN-01 — Health check API endpoints (POST test-connection, GET health)

**Details:**
- Requirements: HEALTH-01, HEALTH-05, HEALTH-06
- Success Criteria:
  1. POST /api/integrations/linear/test-connection triggers fresh health check
  2. Endpoint returns JSON with all individual check results
  3. Overall status field shows healthy/degraded/unhealthy (worst case wins)
  4. GET /api/integrations/linear/health returns cached status without testing
  5. Results cached for rate limiting (respect Linear's 5K req/hr limit)
  6. API keys sanitized from error responses

### Phase 7: Dashboard Integration

**Goal:** Dashboard UI showing integration health with manual test capability
**Depends on:** Phase 6
**Plans:** 1 plan

Plans:

- [x] PLAN-01 — Integrations card with health badge, timestamp, and Test Connection button

**Details:**
- Requirements: DASH-07, DASH-08, DASH-09
- Success Criteria:
  1. Dashboard shows Linear integration health badge (healthy/degraded/unhealthy)
  2. Badge uses color coding (green/yellow/red)
  3. Last-checked timestamp displayed near health status
  4. "Test Connection" button visible on integrations page
  5. Button triggers health check and updates UI with results
  6. Loading state shown during check execution

---

## Milestone Summary

**Key Decisions:**

| Decision | Rationale |
|----------|-----------|
| Dataclasses for health checks | Separate domain logic from persistence (Repository pattern) |
| Synchronous health checks | Avoid Django async/timeout deadlocks |
| Cached health results | Respect Linear API rate limits (5K req/hr) |
| Sanitize error responses | Don't expose API keys in diagnostic output |
| Truncate-then-sanitize pattern | Limit regex processing on long responses |
| Use datetime.now(UTC) | Avoid deprecated utcnow() for Python 3.12+ compatibility |
| Viewer query for auth check | Gets user name/email in one request for both validation and display |
| Rename test_linear_connection to verify_linear_connection | Avoid pytest collection conflict |
| 60s cache TTL | Balance between rate limiting and freshness |
| Reuse existing status classes | Consistent color scheme across dashboard |
| Use x-cloak directive | Prevent flash of unstyled content during Alpine.js init |

**Issues Resolved:**

- Python 3.12+ deprecation warning for datetime.utcnow()
- pytest collection conflict with test_ prefix on production function
- Regex performance on large response bodies (truncate first)

**Issues Deferred:**

- HEALTH-07: Connection test for SLO platform integration (deferred to v4+)
- HEALTH-08: Connection test for CI/CD webhook endpoint (deferred to v4+)
- HEALTH-10-15: Historical tracking and automation (deferred to v4+)

**Technical Debt Incurred:**

None — clean implementation with no shortcuts.

---

_For current project status, see .planning/ROADMAP.md_
_Archived: 2026-01-22 as part of v3 milestone completion_
