# Spec-Trace Linear Integration - Implementation Summary

**Date**: 2025-01-24
**Status**: Implemented
**Commit**: `0a47cdf` - feat: add Linear traceability and conflict detection for requirements

---

## Overview

Integrated requirements traceability into the spec-trace project, connecting Linear issues to tests with automatic conflict detection.

```
Linear Issues    →    Tests    →    CI    →    Alerts
(requirements)       (markers)     (JUnit)    (Slack/Linear)
     ↓                  ↓            ↓            ↓
Requirement  ←─ TestRequirementLink ─→ TestResult ─→ ConflictDetector
```

---

## What Was Built

### 1. New Models (`spectrace/requirements/models.py`)

**TestRequirementLink** - Links test nodeids to Requirements with metadata:
- `test_nodeid`: pytest nodeid (e.g., `tests/test_auth.py::test_login`)
- `requirement`: FK to Requirement
- `last_status`: Status from last test run (passed, failed, error, skipped, unknown)
- `last_run_at`: When this test was last run
- `needs_review`: Flag for manual review needed
- `review_reason`: Reason for review (e.g., 'flaky', 'new link', 'status changed')

**ConflictLog** - Stores detected conflicts between requirements:
- `requirement_a`, `requirement_b`: The two requirements in conflict
- `pattern`: Type of conflict (mutual_exclusion, code_overlap, inverse_correlation)
- `confidence`: Detection confidence (high, medium, low)
- `details`: JSON with analysis data
- `resolved`, `resolved_at`, `resolution_notes`: Resolution tracking

**TestRun Updates** - Added CI metadata fields:
- `git_sha`: Git commit SHA
- `git_branch`: Git branch name
- `ci_job_url`: Link to CI job
- `started_at`, `finished_at`: Timing info

### 2. pytest Plugin (`spectrace/requirements/pytest_plugin.py`)

Extracts `@pytest.mark.linear("CAN-1234")` markers during test collection:
- Outputs to `.spectrace/links.json`
- Activated via `SPECTRACE_EXTRACT_LINKS=1` env var or `--spectrace-extract` flag

### 3. Services

**LinearReporter** (`services/linear_reporter.py`):
- Posts test results as comments on Linear issues
- Manages labels: `tests:linked`, `tests:passing`, `tests:failing`
- Skips closed/completed issues

**ConflictDetector** (`services/conflict_detector.py`):
- Detects mutual exclusion patterns (requirements whose tests never both pass)
- Configurable min_runs and min_overlap thresholds
- Logs conflicts to database with confidence levels

### 4. Management Commands

| Command | Purpose |
|---------|---------|
| `import_test_links` | Import `.spectrace/links.json` into TestRequirementLink records |
| `import_results` | Updated to accept CI metadata (`--git-sha`, `--git-branch`, `--ci-job-url`) |
| `report_to_linear` | Post test results to Linear issues |
| `detect_conflicts` | Detect mutual exclusion conflicts |

### 5. Admin Dashboard (`requirements/admin.py`)

- `TestRequirementLinkAdmin`: Test→requirement mappings with status badges
- `ConflictLogAdmin`: Detected conflicts with confidence badges
- `TestRunAdmin`: Updated with CI metadata display

### 6. Migration

`0007_add_spectrace_models.py` - Adds all new models and fields

---

## Usage Examples

### Marking Tests with Linear Issues

```python
import pytest

@pytest.mark.linear("CAN-1234")
def test_login_flow():
    """Test linked to Linear issue CAN-1234."""
    ...

@pytest.mark.linear("CAN-1234", "CAN-5678")
def test_multi_requirement():
    """Test linked to multiple requirements."""
    ...
```

### CI Integration

```bash
# Extract test-Linear links
SPECTRACE_EXTRACT_LINKS=1 pytest --collect-only -q

# Import links
python manage.py import_test_links .spectrace/links.json

# Run tests and import results with CI metadata
pytest --junitxml=results.xml
python manage.py import_results results.xml \
  --git-sha=${{ github.sha }} \
  --git-branch=${{ github.ref_name }} \
  --ci-job-url=${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

# Report to Linear (on main branch only)
python manage.py report_to_linear --latest

# Detect conflicts
python manage.py detect_conflicts --latest --alert
```

---

## Test Coverage

16 tests in `requirements/tests/test_spectrace.py`:
- TestRequirementLink model tests
- ConflictLog model tests
- TestRun CI metadata tests
- import_test_links command tests
- update_test_requirement_links function tests
- ConflictDetector service tests

---

## Architecture Decisions

### Why TestRequirementLink vs M2M on TestResult?

The existing `TestResult.requirements` M2M tracks which requirements were verified by each test execution. `TestRequirementLink` tracks the *declared* link from pytest markers, with additional metadata:
- Last status (persists across runs)
- Needs review flag (for regressions)
- Review reason

### Why store conflicts in ConflictLog?

Conflict detection is computationally expensive (O(n²) requirement pairs). Storing results allows:
- Periodic batch analysis
- Resolution tracking
- Trend analysis over time

### Linear as Source of Truth

Requirements are imported from Linear (via `import_linear` command). The `external_id` field stores the Linear issue identifier (e.g., "CAN-1234").

---

## Future Enhancements (Not Implemented)

- Code overlap detection (requires coverage.py integration)
- Git blame analysis (PR-level conflict detection)
- Feature flag conflict detection
- Slack alerting integration
- Requirement dependency tracking

---

## Files Changed

### New Files
- `spectrace/requirements/models.py` (updated with new models)
- `spectrace/requirements/pytest_plugin.py`
- `spectrace/requirements/services/__init__.py`
- `spectrace/requirements/services/linear_reporter.py`
- `spectrace/requirements/services/conflict_detector.py`
- `spectrace/requirements/management/commands/import_test_links.py`
- `spectrace/requirements/management/commands/report_to_linear.py`
- `spectrace/requirements/management/commands/detect_conflicts.py`
- `spectrace/requirements/migrations/0007_add_spectrace_models.py`
- `spectrace/requirements/tests/test_spectrace.py`

### Modified Files
- `pyproject.toml` (added `linear` pytest marker)
- `spectrace/requirements/admin.py` (added admin classes)
- `spectrace/requirements/importer.py` (added CI metadata, update_test_requirement_links)
- `spectrace/requirements/management/commands/import_results.py` (added CI args)
