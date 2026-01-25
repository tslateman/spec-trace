# Requirements: SpecTrace v6

**Defined:** 2026-01-25
**Core Value:** PMs can see, at any moment, which requirements are verified by passing tests

## v6 Requirements

Requirements for Impact Analysis & Validation API milestone.

### Impact Analysis

- [ ] **IMPACT-01**: Detect changed requirements from git diff (compare commits/branches)
- [ ] **IMPACT-02**: Return list of tests linked to changed requirements
- [ ] **IMPACT-03**: Propagate impact through hierarchy (parent change → child requirement tests)
- [ ] **IMPACT-04**: Dashboard view showing impact analysis results
- [ ] **IMPACT-05**: CLI command `impact_analysis` for CI pipelines (JSON/text output)

### Validation API

- [ ] **API-01**: GET `/api/validation-runs/` — list runs with filtering (requirement, vendor, status)
- [ ] **API-02**: GET `/api/validation-runs/<id>/` — run detail with steps and results
- [ ] **API-03**: GET `/api/validation-runs/<id>/steps/` — step-level detail with context

## Future Requirements

Deferred to v7+:

- **CI-01**: Webhooks receive test results from CI pipeline
- **CI-02**: Real-time dashboard updates as CI runs complete
- **ANLYT-01**: Historical coverage trends chart

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time impact notifications | Polling/manual refresh acceptable for v6 |
| GraphQL API | REST sufficient, GraphQL adds complexity |
| Webhook push on validation complete | Can add in v7 if needed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMPACT-01 | Phase 1 | Pending |
| IMPACT-02 | Phase 1 | Pending |
| IMPACT-03 | Phase 1 | Pending |
| IMPACT-04 | Phase 2 | Pending |
| IMPACT-05 | Phase 2 | Pending |
| API-01 | Phase 3 | Pending |
| API-02 | Phase 3 | Pending |
| API-03 | Phase 3 | Pending |

**Coverage:**
- v6 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-25*
*Last updated: 2026-01-25 after initial definition*
