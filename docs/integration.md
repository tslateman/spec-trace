# Integrating SpecTrace

Add SpecTrace to your Django project as a dependency.

## Installation

```bash
# pip
pip install git+https://github.com/tslateman/spec-trace.git

# uv
uv pip install git+https://github.com/tslateman/spec-trace.git

# requirements.txt
spectrace @ git+https://github.com/tslateman/spec-trace.git

# pyproject.toml
dependencies = [
    "spectrace @ git+https://github.com/tslateman/spec-trace.git",
]
```

Pin to a specific commit for stability:

```
spectrace @ git+https://github.com/tslateman/spec-trace.git@25c836e
```

## Django Configuration

### settings.py

```python
INSTALLED_APPS = [
    # django-unfold must be before django.contrib.admin
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    # ... other Django apps ...

    # SpecTrace apps
    "treebeard",
    "requirements",
    "spectrace_client",  # Optional: in-app validation SDK
]
```

### urls.py

```python
from django.urls import include, path

urlpatterns = [
    # Your app URLs...

    # SpecTrace admin views (before admin.site.urls)
    path("", include("requirements.urls")),

    path("admin/", admin.site.urls),
]
```

Or selectively include only what you need:

```python
from requirements import api
from requirements.views import matrix_view, validation_run_list_view

urlpatterns = [
    # Just the matrix view
    path("admin/matrix/", matrix_view, name="admin-matrix"),

    # Just the API
    path(
        "api/v1/results/enforcement/",
        api.submit_validation_result,
        name="api-v1-results-enforcement",
    ),
]
```

Keep the `name=` when you wire routes by hand. The redirects that serve the
retired `/api/` paths resolve their targets by URL name, so a route registered
without its name breaks them.

## Public API Surface

### Django Apps

| App                | Purpose                  | Required |
| ------------------ | ------------------------ | -------- |
| `requirements`     | Core traceability engine | Yes      |
| `spectrace_client` | In-app validation SDK    | Optional |

### Models (requirements.models)

**Core models** (stable):

- `Requirement` - Hierarchical requirements with verification status
- `TestRun` - Test execution records
- `TestResult` - Individual test outcomes linked to requirements
- `SLO` - Service Level Objectives linked to requirements
- `InAppValidation` - Validation results from production systems

**Agent coordination** (stable):

- `Agent` - Registered agents with roles
- `AgentTask` - Tasks with claim/review workflow
- `TaskComment` - Review comments on tasks

**Flow tracking** (stable):

- `VerificationFlow` - Multi-step verification flow definitions
- `VerificationFlowRun` - Execution instances
- `VerificationFlowStep` - Individual step outcomes

### Management Commands

```bash
# Spec parsing
python manage.py parse_specs specs/

# Test integration
python manage.py extract_links --output links.json
python manage.py import_results test_results.xml --links links.json
python manage.py validate_links links.json --strict

# SLO integration
python manage.py import_slos slos/
python manage.py update_slo_status --from-json status.json

# In-app validation
python manage.py import_inapp_validations results.json

# Data integrity
python manage.py check_invariants

# Agent coordination
python manage.py agent_register --name my-agent --role coder
python manage.py agent_tasks --status unclaimed
python manage.py agent_claim <task_id> --agent my-agent
```

### REST API Endpoints

Every endpoint lives under `/api/v1/`. The full catalog is in
[docs/api-contract.md](api-contract.md) §2; these are the ones integrators reach for first.

| Endpoint                                 | Method | Purpose                              |
| ---------------------------------------- | ------ | ------------------------------------ |
| `/api/v1/integrations/slo/status/`       | POST   | Update SLO status from observability |
| `/api/v1/results/enforcement/`           | POST   | Submit in-app validation results     |
| `/api/v1/specs/<external_id>/status/`    | GET    | Get requirement verification status  |
| `/api/v1/results/enforcement-runs/`      | GET    | List enforcement runs                |
| `/api/v1/results/enforcement-runs/<id>/` | GET    | Get enforcement run details          |

The Worker guards every `/api/` route with `SPECTRACE_API_KEY`. Send it as
`X-API-Key`, `Authorization: Bearer`, or `Authorization: Api-Key`.

## Linear

The CLI holds the Linear token; no server sees it.

```bash
export LINEAR_API_KEY=lin_api_...

spectrace linear check --workspace acme --team PROJ
spectrace linear pull --label requirement --project spectrace
spectrace linear report junit.xml --links links.json --git-sha "$GITHUB_SHA"
```

`pull` fetches every issue carrying the label, converts each to a requirement,
and pushes the set to the Worker, so a labeled issue reaches the matrix.
`report` reads the same JUnit report CI already pushes, tallies each
requirement's linked cases, and posts the counts as an issue comment plus a
`tests:passing` or `tests:failing` label. `check` verifies the token's shape,
its identity, and its read access, and exits 1 when any check fails.

`pull` upserts. It never deletes, so a requirement parsed from a spec file
survives a pull into the same project.

```bash
curl -X POST https://spectrace.spectrace.workers.dev/api/v1/results/enforcement/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SPECTRACE_API_KEY" \
  -d '{
    "source": "production-app",
    "validations": [
      {"requirement_id": "REQ-AUTH-001", "name": "Login Flow", "status": "success"}
    ]
  }'
```

### Retired `/api/` Paths

The unversioned surface is retired. Old paths redirect to their `/api/v1/`
successor — 301 for GET, HEAD, and OPTIONS, 308 for everything else — and carry
`Deprecation`, `Link`, and `Sunset: Sat, 28 Nov 2026 00:00:00 GMT`. The
redirects are removed after that date, so move your callers to `/api/v1/`.

The GitHub webhook is the exception: `POST /api/webhooks/github/` serves the
same view as `/api/v1/integrations/webhooks/github/` rather than redirecting,
because GitHub records a redirect as a failed delivery and drops the payload.
Point your GitHub App at the `/api/v1/` path.

See [docs/api-contract.md](api-contract.md) §1 for the path-by-path mapping.

### Pytest Marker

```python
import pytest

@pytest.mark.requirement("REQ-AUTH-001")
def test_login():
    pass

@pytest.mark.requirement("REQ-AUTH-001", "REQ-AUTH-002")
def test_login_creates_session():
    pass
```

Register in your `conftest.py` or `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "requirement(*req_ids): link test to requirement IDs",
]
```

### Name Tags

Runners without a marker API link by test name. A bracketed requirement ID
anywhere in the JUnit case name is a link, and the ID normalizes to upper case
with hyphens. `spectrace push --links junit.xml` derives the links and
`spectrace results push junit.xml` derives the results from the same report.

```typescript
describe("POST /login [REQ-AUTH-001]", () => {
  it("[REQ-AUTH-002] refuses a locked account", async () => {});
});
```

Vitest writes the report through its `junit` reporter; gotestsum and
cargo-nextest write the same format for Go and Rust.

## Extending SpecTrace

### Custom Domain Apps

Create a separate Django app for domain-specific features:

```python
# myapp/models.py
from requirements.models import Requirement

class DomainRequirement(models.Model):
    """Domain-specific metadata for requirements."""
    requirement = models.OneToOneField(
        Requirement,
        on_delete=models.CASCADE,
        related_name="domain_data"
    )
    compliance_category = models.CharField(max_length=100)
    review_date = models.DateField(null=True)
```

### Custom Flows

Register verification flows for your domain:

```python
# myapp/flows.py
from dataclasses import dataclass

@dataclass
class FlowDefinition:
    name: str
    display_name: str
    description: str
    steps: list[str]
    version: int = 1

MY_DOMAIN_FLOW = FlowDefinition(
    name="my_domain_flow",
    display_name="My Domain Process",
    description="Multi-step verification for my domain",
    steps=[
        "Initialize",
        "Validate Input",
        "Process",
        "Verify Output",
        "Complete",
    ],
)
```

## Version Compatibility

SpecTrace is pre-1.0, so minor versions may change the surface. Current
version: **0.11.0** (`pyproject.toml`).

| SpecTrace | Python | Django |
| --------- | ------ | ------ |
| 0.11.x    | ≥3.12  | 5.2.x  |
