# SpecTrace

## What This Is

A requirements traceability system that connects product specs to verified code. Specs live in the codebase as markdown files with YAML frontmatter, pytest tests are annotated with requirement IDs via `@pytest.mark.requirement("REQ-XXX")`, and a Django dashboard shows PMs, engineers, and QA which requirements are actually verified by passing tests.

## Core Value

PMs can see, at any moment, which requirements are verified by passing tests — eliminating the gap between "what we think we built" and "what we actually built."

## Current Milestone: v3 Integration Health Checks

**Goal:** Monitor external integration health with granular diagnostic checks — enabling proactive detection of connectivity issues with Linear, SLO platforms, and CI/CD systems.

**Target features:**
- Connection testing endpoints for each integration
- Granular diagnostic checks (auth, reachability, permissions)
- Dashboard health status display with timestamps
- Historical health tracking for debugging

## What's Shipped

### v2 Traceability Matrix (Shipped: 2026-01-21)

- **Matrix view:** Paginated grid (requirements × tests) with color-coded cells
- **Filtering:** Status, tags, parent requirement filters
- **Export:** CSV export respecting filters
- **Dashboard tab:** Integrated in django-unfold admin

### v1 MVP (Shipped: 2026-01-21)

**Lines of code:** 5,201 Python
**Tech stack:** Django 5.2, django-treebeard, django-unfold, pytest, junitparser

- **Spec parsing:** Markdown files with YAML frontmatter → hierarchical requirements
- **Test linking:** `@pytest.mark.requirement("REQ-XXX")` decorator → JSON links
- **Status computation:** JUnit XML import → passing/failing/untested per requirement
- **Dashboard:** Metrics banner + hierarchical tree with status indicators
- **Navigation:** Bidirectional (requirement ↔ tests)
- **Validation:** CI command to detect drift between tests and requirements
- **Extended:** REST API, Linear integration, in-app validation, SLO support

## Requirements

### Validated

- ✓ SPEC-01: Spec parsing from markdown — v1
- ✓ SPEC-02: Unique IDs (REQ-XXX format) — v1
- ✓ SPEC-03: Hierarchical requirements — v1
- ✓ SPEC-04: Tag filtering — v1
- ✓ SPEC-05: Git versioning — v1
- ✓ LINK-01: pytest @requirement decorator — v1
- ✓ LINK-02: Multiple tests → one requirement — v1
- ✓ LINK-03: One test → multiple requirements — v1
- ✓ LINK-04: extract_links command — v1
- ✓ VERIFY-01: Verification status (passing/failing/untested) — v1
- ✓ VERIFY-02: Status derivation from test results — v1
- ✓ VERIFY-03: JUnit XML import — v1
- ✓ DASH-01: Hierarchical dashboard — v1
- ✓ DASH-02: Summary metrics — v1
- ✓ DASH-04: Coverage gap highlighting — v1
- ✓ DASH-05: Search by ID/text/status/tag — v1
- ✓ DASH-06: Filter by category/tag — v1
- ✓ NAV-01: Requirement → linked tests — v1
- ✓ NAV-02: Test → linked requirements — v1

### Active (v3)

- [ ] HEALTH-01: Connection testing endpoints for integrations
- [ ] HEALTH-02: Granular diagnostic checks (auth, reachability, permissions)
- [ ] HEALTH-03: Dashboard health status display
- [ ] HEALTH-04: Historical health tracking

### Future (v4+)

- [ ] NAV-03: Impact analysis (spec change → affected tests)
- [ ] CI-01: Webhooks receive test results from CI pipeline
- [ ] CI-02: Real-time dashboard updates as CI runs complete
- [ ] ANLYT-01: Historical coverage trends chart

### Out of Scope

- Built-in test execution — consume results, don't run tests
- Electronic signatures — not targeting compliance
- Complex approval workflows — enterprise overhead
- Real-time collaborative editing — git handles this
- Multi-repo aggregation — single repo focus
- AI requirement generation — requirements need human judgment

## Context

**Problem solved:**
- Specs scattered across Slack, Notion, Linear, meetings → specs in codebase
- No way to answer "is requirement X implemented and working?" → dashboard shows status
- Tests may verify wrong behavior → explicit requirement linking

**Tech choices:**
- Django for dashboard (Python ecosystem, team familiarity)
- treebeard for hierarchy (efficient tree queries without recursive SQL)
- django-unfold for modern UI (Tailwind-based admin)
- pytest markers for test linking (native to existing workflow)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Specs in codebase, not Notion | Version control, no drift, reviewable changes | ✓ Good |
| Markdown format | Human-readable, easy for PMs to write/review | ✓ Good |
| pytest annotations | Native to existing test workflow | ✓ Good |
| Django for dashboard | Stays in Python ecosystem, team familiarity | ✓ Good |
| django-treebeard for hierarchy | Efficient tree queries, no recursive SQL | ✓ Good |
| Denormalized verification_status | Fast dashboard reads, recompute on import | ✓ Good |
| Deferred traceability matrix | Bidirectional navigation sufficient for v1 | ✓ Shipped in v2 |
| Dataclasses for health checks | Separate domain logic from persistence (Repository pattern) | — Pending (v3) |
| Synchronous health checks | Avoid Django async/timeout deadlocks | — Pending (v3) |
| Cached health results | Respect Linear API rate limits (5K req/hr) | — Pending (v3) |

---
*Last updated: 2026-01-21 after v3 milestone start*
