# Roadmap: v3 Integration Health Checks

## Overview

v3 adds integration health monitoring with granular diagnostic checks for Linear. The system tests configuration, authentication, and permissions, exposes results via API endpoints, and displays health status in the dashboard with manual testing capability.

## Phases

**Phase Numbering:**
- Integer phases (5, 6, 7): Planned v3 milestone work
- Decimal phases (e.g., 5.1): Urgent insertions (marked with INSERTED)
- v3 continues from v2 (which ended at phase 4)

- [ ] **Phase 5: Health Check Foundation** - Domain objects and diagnostic check implementations
- [ ] **Phase 6: API Endpoints** - Test connection endpoints with status aggregation
- [ ] **Phase 7: Dashboard Integration** - Health status display and manual testing UI

## Phase Details

### Phase 5: Health Check Foundation
**Goal:** Core domain objects and granular diagnostic checks for Linear integration
**Depends on:** v2 complete
**Requirements:** HEALTH-02, HEALTH-03, HEALTH-04
**Success Criteria** (what must be TRUE):
  1. VerificationCheck dataclass exists with name, passed, details, timestamp fields
  2. TestConnectionResult dataclass aggregates multiple checks
  3. Configuration check validates Linear API key, workspace, and team presence
  4. Authentication check makes actual API request to verify token validity
  5. Permissions check verifies read access to issues endpoint
  6. Failed checks include error_message and sanitized response details
**Plans:** TBD

### Phase 6: API Endpoints
**Goal:** REST endpoints for triggering health checks and retrieving cached status
**Depends on:** Phase 5
**Requirements:** HEALTH-01, HEALTH-05, HEALTH-06
**Success Criteria** (what must be TRUE):
  1. POST /api/integrations/linear/test-connection triggers fresh health check
  2. Endpoint returns JSON with all individual check results
  3. Overall status field shows healthy/degraded/unhealthy (worst case wins)
  4. GET /api/integrations/linear/health returns cached status without testing
  5. Results cached for rate limiting (respect Linear's 5K req/hr limit)
  6. API keys sanitized from error responses
**Plans:** TBD

### Phase 7: Dashboard Integration
**Goal:** Dashboard UI showing integration health with manual test capability
**Depends on:** Phase 6
**Requirements:** DASH-07, DASH-08, DASH-09
**Success Criteria** (what must be TRUE):
  1. Dashboard shows Linear integration health badge (healthy/degraded/unhealthy)
  2. Badge uses color coding (green/yellow/red)
  3. Last-checked timestamp displayed near health status
  4. "Test Connection" button visible on integrations page
  5. Button triggers health check and updates UI with results
  6. Loading state shown during check execution
**Plans:** TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Health Check Foundation | 0/TBD | Not started | - |
| 6. API Endpoints | 0/TBD | Not started | - |
| 7. Dashboard Integration | 0/TBD | Not started | - |

---
*Roadmap created: 2026-01-21*
*Milestone: v3 Integration Health Checks*
