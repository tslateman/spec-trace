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

## Writing Specs

Create markdown files in `specs/` with frontmatter:

```markdown
---
id: REQ-AUTH-001
title: User Login
priority: high
tags: [authentication, security]
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

## Verification Status

- **Passing** - All linked tests pass
- **Failing** - Any linked test fails
- **Untested** - No tests linked to requirement

## License

MIT
