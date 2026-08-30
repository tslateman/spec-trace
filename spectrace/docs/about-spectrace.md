# SpecTrace

Connect product specs to verified code.

## The Problem

You gather requirements. You write tests.
Over time, actuality drifts from specification.
Does behavior match the intent? How is the feature supposed to work? Nobody knows.

[Requirements traceability](https://en.wikipedia.org/wiki/Requirements_traceability) solves this by linking specs to code to tests.

**SpecTrace brings this to Python: specs-as-code, pytest integration, live verification dashboard.**

## Core Capabilities

| Capability              | Description                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------- |
| **Specs as Code**       | Requirements live in your repo as markdown. Version controlled, reviewable, no drift. |
| **Test Linking**        | Link tests to requirements with `@pytest.mark.requirement` decorators.                |
| **Verification Status** | Live dashboard shows which requirements are passing, failing, or untested.            |
| **Hierarchical**        | Organize requirements in parent-child trees. Efficient materialized path queries.     |
| **Impact Analysis**     | See which tests are affected when specs change via git diff integration.              |
| **Traceability Matrix** | Visual grid of requirements × tests with color-coded verification status.             |

## Why Traceability Matters

### Without Traceability

- Specs scattered across Slack, Notion, Linear
- No single source of truth
- Can't answer "is REQ-X working?"
- Tests may verify wrong behavior
- Coverage gaps go unnoticed
- Specs drift from implementation

### With SpecTrace

- Specs version-controlled with code
- Single source of truth in repo
- One-click verification status
- Explicit requirement ↔ test links
- Dashboard highlights coverage gaps
- Specs stay in sync via git workflow

## Spec-Driven Development

Agents forget between sessions. They can't infer from incomplete information.
Specifications become **executable context**: instructions agents read before writing code.

> **Specs define intent. Agents implement. Tests validate. Humans authorize.**
>
> The spec is the source of truth. Code is cheap; design and validation are the bottlenecks.
> SpecTrace links specs to tests to verification status.

See [Spec-Driven Development](spec-driven-development.md) for the full methodology.

## When to Spec

Not everything needs a spec. Match format to complexity.

**Skip specs for simple tasks** — UI tweaks, content updates, obvious bug fixes. Plain language in the commit message is enough.

**Use specs for complex work** — Business logic, multi-step flows, integrations, anything with edge cases worth documenting.

**Focus on outcomes, not implementation** — Describe what the system does, not how it does it. Prioritize user-visible behavior over technical recipes.

## How It Works

```
Write Specs → Link Tests → Run Tests → Import → Dashboard
(markdown)    (@pytest)    (JUnit XML)  (CLI)    (live status)
```

### Key Concepts

**Requirement** — Product spec parsed from markdown with unique ID (REQ-XXX-001). Organized hierarchically with parent-child relationships.

**Verification Status** — Passing: all linked tests pass. Failing: any test fails. Untested: no tests linked.

**Traceability** — Bidirectional links between requirements ↔ tests. Navigate from requirement to tests, or from test to requirements.

**Impact Analysis** — Git diff integration shows which tests are affected when specs change. Helps target test runs efficiently.

## Getting Started

### 1. Create a Spec File

Create `specs/auth.md` with YAML frontmatter:

```yaml
---
id: REQ-AUTH-001
title: User Login
priority: high
verification_method: test
---

Users must be able to log in with email and password.

## Acceptance Criteria
- Email validation
- Password strength requirements
- Session creation on success
```

### 2. Import Specs

Parse markdown files into the database:

```bash
python manage.py parse_specs specs/
```

### 3. Link Tests

Annotate pytest tests with requirement IDs:

```python
import pytest

@pytest.mark.requirement("REQ-AUTH-001")
def test_user_can_login():
    """Test successful login with valid credentials."""
    pass

@pytest.mark.requirement("REQ-AUTH-001", "REQ-AUTH-002")
def test_login_creates_session():
    """Test can link to multiple requirements."""
    pass
```

### 4. Run Tests & Import Results

```bash
pytest --junitxml=results.xml
python manage.py extract_links -o links.json
python manage.py import_results results.xml --links links.json
```

### 5. View Dashboard

```bash
python manage.py runserver
# Open http://localhost:8000/admin/
```

## Advanced Features

| Feature                | Description                                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Vendor Coverage**    | Track integration validation by vendor. See pass rates per PMS, mobile key provider, or payment gateway.         |
| **In-App Validation**  | SDK for validation buttons in production apps. Multi-step validations with granular pass/fail tracking.          |
| **SLO Integration**    | Link requirements to Service Level Objectives using OpenSLO YAML. Track operational compliance.                  |
| **REST API**           | Push validation results from external systems. Submit status updates, retrieve requirement status.               |
| **Conflict Detection** | FRET-inspired structured fields enable condition overlap, timing conflict, and response contradiction detection. |
| **Linear Integration** | Sync with Linear issues. Track requirement-to-issue mapping with health checks and auto-enrichment.              |
| **Invariant Checks**   | Runtime verification that status computations remain consistent. Detect and fix data corruption.                 |
| **Drift Detection**    | Find stale links, orphan requirements, unmarked tests, and spec files modified after last test run.              |

## Tech Stack

### Core Technologies

- **Django 5.2 LTS** — Web framework
- **django-treebeard** — Hierarchical storage (materialized path)
- **django-unfold** — Modern admin UI
- **pytest** — Test framework with markers
- **SQLite/PostgreSQL** — Database

### Design Philosophy

- **Specs in codebase, not Notion** — version control brings review, history, branches
- **Markdown format** — PM-friendly, reviewable in PRs
- **pytest markers** — native to existing workflow, no new test runner
- **Denormalized status** — fast dashboard reads, computed on import
- **Materialized path** — efficient tree queries without recursive CTEs

## CLI Commands

### Spec Management

```bash
python manage.py parse_specs specs/           # Import specs from markdown
python manage.py validate_links links.json    # Check for unknown requirement IDs
```

### Test Results

```bash
python manage.py extract_links -o links.json  # Extract requirement markers from tests
python manage.py import_results results.xml   # Import JUnit XML results
```

### Analysis

```bash
python manage.py impact_analysis BASE HEAD    # Show affected tests for spec changes
python manage.py check_invariants             # Verify status consistency
python manage.py detect_drift                 # Find stale links and orphan requirements
```

### SLO

```bash
python manage.py import_openslo slo.yaml      # Import OpenSLO definitions
```

## Verification Methods

Requirements can specify how they should be verified:

| Method        | Meaning                                   |
| ------------- | ----------------------------------------- |
| `test`        | Verified by pytest tests only             |
| `inapp`       | Verified by in-app validation only        |
| `both`        | Must pass both test and in-app validation |
| `unspecified` | Use whatever is available (default)       |

## Status Computation

Verification status follows these rules:

1. **SLO Override**: Breached SLO → always `failing`
2. **Test Results**: Any fail/error → `failing`, all pass → `passing`, no tests → `untested`
3. **In-App Validation**: Same logic as tests
4. **Verification Method**: Determines which sources count

## Project Structure

```
specs/                    # Requirement markdown files
  auth/
    login.md
    logout.md
  payments/
    checkout.md
tests/                    # pytest tests with @requirement markers
  test_auth.py
  test_payments.py
spectrace/                # Django project
  requirements/           # Core app
    models.py             # Requirement, TestResult, etc.
    status.py             # Status computation
    invariants.py         # Consistency checks
    validator.py          # Drift detection
```

## API Endpoints

| Endpoint                            | Method | Description                         |
| ----------------------------------- | ------ | ----------------------------------- |
| `/api/v1/specs/<id>/status/`        | GET    | Get requirement verification status |
| `/api/v1/integrations/slo/status/`  | POST   | Update SLO status                   |
| `/api/v1/results/enforcement/`      | POST   | Submit in-app validation result     |
| `/api/v1/results/enforcement-runs/` | GET    | List enforcement runs               |
| `/api/openapi.json`                 | GET    | OpenAPI specification               |
| `/api/docs/`                        | GET    | Swagger UI                          |

The unversioned `/api/` paths are retired and redirect to their `/api/v1/`
successor until 2026-11-28. `docs/api-contract.md` has the full catalog.
