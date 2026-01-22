# SpecTrace

Requirements traceability for Python projects. Connect specs to tests, see what's verified.

## Quick Start

```bash
# Install
pip install -e .

# Setup database
cd spectrace
python manage.py migrate
python manage.py createsuperuser

# Import your specs
python manage.py parse_specs ../specs/

# Run tests with JUnit output
pytest tests/ --junitxml=test_results.xml

# Extract test-requirement links
python manage.py extract_links --output links.json

# Import results and compute status
python manage.py import_results test_results.xml --links links.json

# View dashboard
python manage.py runserver
# Open http://localhost:8000/admin/
```

## Examples

See the **[Document Pipeline Example](examples/document-pipeline/)** for a comprehensive demonstration of spec-trace features:

- Nested requirement hierarchy (3 levels)
- Multiple verification methods (test, inapp, both)
- Passing, failing, and skipped tests
- SLO integration with OpenSLO YAML
- Various pytest patterns (parametrized, async, class-based, xfail)
- CI/CD workflow example

Run the demo:
```bash
python scripts/demo_pipeline.py
```

## Writing Specs

Create markdown files in `specs/` with frontmatter:

```markdown
---
id: REQ-AUTH-001
title: User Login
priority: high
tags: [authentication, security]
verification_method: test  # test, inapp, or both
---

Users must be able to log in with email and password.
```

## Linking Tests

Use the `@pytest.mark.requirement` decorator:

```python
import pytest

@pytest.mark.requirement("REQ-AUTH-001")
def test_user_can_login():
    # test implementation
    pass

@pytest.mark.requirement("REQ-AUTH-001", "REQ-AUTH-002")
def test_login_creates_session():
    # test can link to multiple requirements
    pass
```

## Commands

| Command | Description |
|---------|-------------|
| `parse_specs <dir>` | Import requirements from markdown specs |
| `extract_links` | Extract test-requirement links from test files |
| `import_results <xml>` | Import pytest JUnit XML and compute status |
| `validate_links <json>` | Validate links for drift detection (CI) |
| `import_slos <dir>` | Import SLOs from OpenSLO YAML files |
| `update_slo_status --from-json <file>` | Update SLO status from observability data |
| `import_inapp_validations <json>` | Import in-app validation results |

## Verification Status

- **Passing** - All linked tests pass
- **Failing** - Any linked test fails
- **Untested** - No tests linked to requirement

## Verification Methods

Requirements can specify how they should be verified:

- **test** - Verified by automated tests (default)
- **inapp** - Verified by in-app validation buttons/endpoints
- **both** - Must pass both test and in-app validation

## SLO Integration

Link requirements to Service Level Objectives using OpenSLO YAML:

```yaml
apiVersion: openslo/v1
kind: SLO
metadata:
  name: api-availability
  labels:
    requirement: REQ-API-001
spec:
  service: api-gateway
  objectives:
    - target: 0.999
      timeWindow:
        duration: 30d
```

Import with: `python manage.py import_slos slos/`

## REST API

External systems can push status updates:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/slo/status/` | POST | Update SLO status from observability platforms |
| `/api/validation/result/` | POST | Submit in-app validation results |
| `/api/requirement/<id>/status/` | GET | Get requirement verification status |

### Example: Update SLO Status

```bash
curl -X POST http://localhost:8000/api/slo/status/ \
  -H "Content-Type: application/json" \
  -d '{
    "slos": [
      {"name": "api-availability", "status": "met", "current_value": 0.9995}
    ]
  }'
```

### Example: Submit Validation Result

```bash
curl -X POST http://localhost:8000/api/validation/result/ \
  -H "Content-Type: application/json" \
  -d '{
    "source": "production-app",
    "validations": [
      {"requirement_id": "REQ-AUTH-001", "name": "Login Flow", "status": "success"}
    ]
  }'
```

## CI Integration

Validate test-requirement links in CI to catch drift:

```bash
python manage.py validate_links links.json --strict
```

- `--strict` - Exit with error on warnings (missing coverage)
- `--format json` - Output JSON for programmatic parsing

## License

MIT
