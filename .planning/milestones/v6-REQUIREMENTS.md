# Requirements Archive: SpecTrace v6 — Impact Analysis & Validation API

**Defined:** 2026-01-25
**Completed:** 2026-01-25
**Core Value:** PMs can see, at any moment, which requirements are verified by passing tests

## v6 Requirements (All Complete)

### Impact Analysis

- [x] **IMPACT-01**: Detect changed requirements from git diff (compare commits/branches)
  - *Implemented in:* `services/impact_analyzer.py`
  - *Tests:* `test_impact_analyzer.py`

- [x] **IMPACT-02**: Return list of tests linked to changed requirements
  - *Implemented in:* `services/impact_analyzer.py`
  - *Tests:* `test_impact_analyzer.py`

- [x] **IMPACT-03**: Propagate impact through hierarchy (parent change → child requirement tests)
  - *Implemented in:* `services/impact_analyzer.py` using treebeard `get_descendants()`
  - *Tests:* `test_impact_analyzer.py`

- [x] **IMPACT-04**: Dashboard view showing impact analysis results
  - *Implemented in:* `views.py` + `templates/admin/requirements/impact_analysis.html`
  - *Tests:* Manual verification (Alpine.js UI)

- [x] **IMPACT-05**: CLI command `impact_analysis` for CI pipelines (JSON/text output)
  - *Implemented in:* `management/commands/impact_analysis.py`
  - *Tests:* `test_impact_analysis_command.py`

### Validation API

- [x] **API-01**: GET `/api/validation-runs/` — list runs with filtering (requirement, vendor, status)
  - *Implemented in:* `api.py`
  - *Tests:* `test_validation_api.py`

- [x] **API-02**: GET `/api/validation-runs/<id>/` — run detail with steps and results
  - *Implemented in:* `api.py`
  - *Tests:* `test_validation_api.py`

- [x] **API-03**: GET `/api/validation-runs/<id>/steps/` — step-level detail with context
  - *Implemented in:* `api.py`
  - *Tests:* `test_validation_api.py`

## Traceability Summary

| Requirement | Phase | Status | Outcome |
|-------------|-------|--------|---------|
| IMPACT-01 | 12 | Complete | Validated by tests |
| IMPACT-02 | 12 | Complete | Validated by tests |
| IMPACT-03 | 12 | Complete | Validated by tests |
| IMPACT-04 | 13 | Complete | Validated manually |
| IMPACT-05 | 13 | Complete | Validated by tests |
| API-01 | 14 | Complete | Validated by tests |
| API-02 | 14 | Complete | Validated by tests |
| API-03 | 14 | Complete | Validated by tests |

**Coverage:**
- Total requirements: 8
- Implemented: 8
- Test-validated: 7 (IMPACT-04 is UI, validated manually)
- Dropped/Adjusted: 0

## Deferred Requirements (v7+)

These requirements were identified during v6 but deferred:

- **CI-01**: Webhooks receive test results from CI pipeline
- **CI-02**: Real-time dashboard updates as CI runs complete
- **ANLYT-01**: Historical coverage trends chart

## Out of Scope (Confirmed)

| Feature | Reason |
|---------|--------|
| Real-time impact notifications | Polling/manual refresh acceptable for v6 |
| GraphQL API | REST sufficient, GraphQL adds complexity |
| Webhook push on validation complete | Can add in v7 if needed |

---
*Archived: 2026-01-25*
