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
| `/api/v1/integrations/linear/health/`    | GET    | Linear integration health check      |

`POST /api/v1/integrations/slo/status/` and `POST /api/v1/results/enforcement/`
require an API key once `SPECTRACE_API_KEY` is set. Send it as `X-API-Key`:

```bash
curl -X POST http://localhost:8000/api/v1/results/enforcement/ \
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

SpecTrace follows semantic versioning once stable. Current version: **0.1.0** (pre-release).

| SpecTrace | Python | Django |
| --------- | ------ | ------ |
| 0.1.x     | ≥3.12  | 5.2.x  |
