# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-19)

**Core value:** PMs can see, at any moment, which requirements are verified by passing tests
**Current focus:** Phase 4 - Advanced Features (Phase 3 complete)

## Current Position

Phase: 4 of 4 (Dashboard Features & Navigation)
Plan: Bidirectional navigation implemented
Status: Core milestone complete, extending with verification features
Last activity: 2026-01-21 - Added in-app validation and SLO tracking models

Progress: [########--] 80% (core features complete)

### Recent Additions (beyond original roadmap)
- Link validation command for CI drift detection
- In-app validation models for product UI verification
- SLO tracking models for observability integration
- Verification method field (test/inapp/both)

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 3.4 min
- Total execution time: 17 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 2 | 6 min | 3 min |
| 02-test-integration | 1 | 5 min | 5 min |
| 03-verification-dashboard | 2 | 6 min | 3 min |

**Recent Trend:**
- Last 5 plans: 01-01 (4 min), 01-02 (2 min), 02-01 (5 min), 03-01 (3 min), 03-02 (3 min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

| Decision | Phase | Rationale |
|----------|-------|-----------|
| django-treebeard MP_Node for hierarchy | 01-01 | Efficient ancestor/descendant queries without recursive SQL |
| SQLite for development | 01-01 | Simple setup, sufficient for local development |
| external_id as unique requirement key | 01-01 | IDs from spec frontmatter must be unique across all specs |
| JSONField for tags | 01-01 | Flexible list storage without separate table |
| Explicit parent references in frontmatter | 01-02 | Child requirements specify parent: REQ-XXX rather than folder structure |
| Graceful missing parent handling | 01-02 | Missing parent refs create root nodes with warning, not failure |
| Verification as computed, not stateful | context | Status derived from test results, not FSM (from workflow research) |
| Dual marker registration (conftest + pyproject) | 02-01 | Ensures marker works in both programmatic and IDE contexts |
| Disable pytest-django during collection | 02-01 | Avoids DB blocking when extracting test-requirement links |
| Unknown requirement IDs produce warnings | 02-01 | Non-blocking validation - allows tests to run before specs exist |
| Denormalized verification_status on Requirement | 03-01 | Fast dashboard queries, recomputed on import |
| ManyToMany for test-requirement links | 03-01 | One test can verify multiple requirements and vice versa |
| unfold.admin.ModelAdmin for all admin classes | 03-02 | Consistent modern styling over TreeAdmin |
| Dashboard callback for custom metrics | 03-02 | Inject context variables to admin index template |
| Yellow background for untested requirements | 03-02 | Makes coverage gaps visible at a glance |
| validate_links command for CI | 04 | Catches drift early - unknown reqs are errors, missing coverage is warning |
| InAppValidation model | 04 | Support requirements verified by product UI buttons |
| SLO model linked to requirements | 04 | Track which requirements are backed by observability SLOs |
| verification_method field | 04 | Explicit classification: test, inapp, or both |

### External Context

Research from Canary Better Specs initiative integrated 2026-01-20:
- `research/BETTER_SPECS_CONTEXT.md` - Traceability pipeline, drift detection patterns
- `research/WORKFLOW_PATTERNS.md` - FSM library evaluation (conclusion: not needed)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-01-21
Stopped at: Committed in-app validation and SLO tracking models
Resume file: None

### Recent Commits
- d0ba512: test: add unit and integration tests for link validation
- 33d05e0: feat: add in-app validation and SLO tracking models
