# Agent Guidelines for SpecTrace

This document provides coding guidelines and conventions for AI coding agents working in the SpecTrace repository. SpecTrace is a requirements traceability system connecting product specs (markdown files) to verified code through pytest test annotations and a Django dashboard.

## Project Overview

- **Language**: Python 3.12+ (currently using 3.13)
- **Framework**: Django 5.2 LTS
- **Database**: SQLite (development), PostgreSQL recommended for production
- **Testing**: pytest 9.x with pytest-django
- **Key Dependencies**: django-treebeard (hierarchical requirements), python-frontmatter (spec parsing), Markdown

## Commands

### Testing
```bash
# Run all tests
make test
# or
pytest

# Run specific test file
pytest path/to/test_file.py

# Run specific test function
pytest path/to/test_file.py::test_function_name

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "pattern"
```

### Development Server
```bash
# Start Django development server
make run
# or
python spectrace/manage.py runserver

# Django shell
make shell
# or
python spectrace/manage.py shell
```

### Database
```bash
# Run migrations
make migrate
# or
python spectrace/manage.py migrate

# Create new migrations
make makemigrations
# or
python spectrace/manage.py makemigrations

# Parse spec files into database
python spectrace/manage.py parse_specs specs/
python spectrace/manage.py parse_specs specs/ --clear  # Clear existing first
python spectrace/manage.py parse_specs specs/ --dry-run  # Validate without saving
```

### Installation
```bash
# Install package in editable mode
make install
# or
pip install -e .

# Install with dev dependencies
make install-dev
# or
pip install -e ".[dev]"
```

### Cleanup
```bash
# Remove caches and build artifacts
make clean
```

## Code Style Guidelines

### General Python Style

- **Style Guide**: Follow PEP 8 conventions
- **Line Length**: 100 characters max (inferred from existing code)
- **Indentation**: 4 spaces (no tabs)
- **String Quotes**: Single quotes for strings, double quotes for docstrings and when avoiding escapes
- **Blank Lines**: Two blank lines between top-level classes/functions, one between methods

### Imports

Order imports in three groups separated by blank lines:
1. Standard library imports
2. Third-party imports (Django, pytest, etc.)
3. Local application imports

```python
# Standard library
import re
from pathlib import Path
from typing import Any

# Third-party
import frontmatter
from django.db import models

# Local
from requirements.models import Requirement
```

### Naming Conventions

- **Classes**: PascalCase (e.g., `SpecParser`, `Requirement`)
- **Functions/Methods**: snake_case (e.g., `parse_file`, `import_to_database`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `REQ_HEADING_PATTERN`, `BASE_DIR`)
- **Private methods**: Prefix with single underscore (e.g., `_parse_single`, `_parse_multi`)
- **Module-level variables**: snake_case

### Type Hints

Use type hints for function signatures, especially for complex types:

```python
def parse_file(self, file_path: Path) -> list[dict[str, Any]]:
    """Parse a single spec file, return list of requirement dicts."""
    ...
```

Use modern syntax (Python 3.9+):
- `list[Type]` instead of `List[Type]`
- `dict[K, V]` instead of `Dict[K, V]`
- `Type | None` instead of `Optional[Type]`

### Docstrings

Use triple double-quotes for all docstrings. Follow Google/NumPy style:

```python
"""Short one-line summary.

Longer description if needed. Can span multiple paragraphs.

Args:
    param_name: Description of parameter
    another_param: Description of another parameter

Returns:
    Description of return value

Raises:
    ExceptionType: When this exception is raised
"""
```

For single-line docstrings:
```python
"""Parse a single spec file, return list of requirement dicts."""
```

### Django Models

- Use `verbose_name` and `verbose_name_plural` in Meta class
- Include `help_text` for fields to document their purpose
- Implement `__str__` method for readable representations
- Use descriptive field names that explain the data stored
- Use `JSONField` for flexible metadata, not proliferating columns

```python
class Requirement(MP_Node):
    """A requirement parsed from a spec markdown file."""
    
    external_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique ID from spec file (e.g., REQ-AUTH-001)"
    )
    
    class Meta:
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"
    
    def __str__(self):
        return f"{self.external_id}: {self.title}"
```

### Django Management Commands

- Inherit from `BaseCommand`
- Set descriptive `help` text
- Use `add_arguments` for CLI arguments
- Implement core logic in `handle` method
- Use `CommandError` for user-facing errors
- Use `self.stdout.write()` for output, `self.style.SUCCESS()` for colored messages

### Error Handling

- Let exceptions propagate for programming errors (AttributeError, KeyError, etc.)
- Catch and handle expected errors gracefully (file not found, validation errors)
- Log warnings for non-fatal issues (e.g., failed to parse individual file) but continue processing
- Use specific exceptions over bare `except:`

```python
try:
    file_requirements = self.parse_file(md_file)
    requirements.extend(file_requirements)
except Exception as e:
    # Log warning but continue parsing other files
    print(f"Warning: Failed to parse {md_file}: {e}")
```

### Testing

- Place tests adjacent to code being tested (not in separate tests/ directory)
- Use pytest conventions: `test_*.py` or `*_test.py` files
- Name test functions with `test_` prefix
- Use descriptive test names that explain what is being tested
- Configure pytest via `pyproject.toml` under `[tool.pytest.ini_options]`
- Use pytest fixtures for shared setup
- Future: Use `@pytest.mark.requirement("REQ-XXX")` to link tests to requirements

### File Paths

- Use `pathlib.Path` instead of `os.path`
- Construct paths with `/` operator: `BASE_DIR / 'subdir' / 'file.py'`
- Use `Path.glob('**/*.md')` for recursive file finding
- Convert to string only when necessary: `str(file_path)`

### Django Settings

- Use `Path` for directory paths (not strings)
- Set `BASE_DIR = Path(__file__).resolve().parent.parent`
- Keep development settings simple, production settings separate
- Use environment variables for secrets in production

## Project Structure

```
spec-trace/
├── spectrace/              # Django project root
│   ├── spectrace/          # Django settings package
│   │   ├── settings.py     # Django configuration
│   │   ├── urls.py         # URL routing
│   │   └── wsgi.py         # WSGI configuration
│   ├── requirements/       # Main Django app
│   │   ├── models.py       # Requirement model (django-treebeard)
│   │   ├── parser.py       # SpecParser class for parsing markdown
│   │   ├── admin.py        # Django admin configuration
│   │   └── management/
│   │       └── commands/
│   │           └── parse_specs.py  # CLI command for importing specs
│   ├── manage.py           # Django management script
│   └── db.sqlite3          # SQLite database (ignored in git)
├── specs/                  # Spec markdown files
│   ├── example.md          # Example requirement spec
│   └── auth/               # Feature-specific specs
│       ├── login.md
│       └── register.md
├── .planning/              # Project planning documents (internal use)
├── pyproject.toml          # Python project metadata & dependencies
├── Makefile                # Common development commands
└── .gitignore              # Git ignore patterns
```

## Spec File Format

Specs are markdown files with YAML frontmatter. Two formats supported:

### Single Requirement File
```markdown
---
id: REQ-AUTH-001
title: User Login
tags: [auth, security]
priority: high
status: active
---

Users must be able to log in with email and password.

## Acceptance Criteria
- Email validation
- Password strength requirements
```

### Multi-Requirement File
```markdown
---
tags: [auth]
priority: high
status: active
---

## REQ-AUTH-001: User Login

Login functionality description...

## REQ-AUTH-002: User Logout

Logout functionality description...
```

## Key Architectural Decisions

- **Specs in codebase**: Markdown files live in `specs/` directory, version-controlled with code
- **Hierarchical storage**: Uses django-treebeard's materialized path for efficient tree queries
- **Parser design**: SpecParser extracts YAML frontmatter + markdown content, handles both single and multi-requirement files
- **Test linking**: Future pytest markers (`@pytest.mark.requirement("REQ-XXX")`) will link tests to requirements
- **Simple state**: Requirement verification status computed from test results, not stored as state machine

## Common Tasks

### Adding a New Field to Requirement Model
1. Edit `spectrace/requirements/models.py` to add field
2. Run `make makemigrations` to create migration
3. Run `make migrate` to apply migration
4. Update parser if field should come from spec frontmatter

### Adding a New Management Command
1. Create file in `spectrace/requirements/management/commands/`
2. Inherit from `BaseCommand`
3. Set `help` text and implement `add_arguments` and `handle` methods

### Parsing New Specs
1. Add markdown files to `specs/` directory following format above
2. Run `python spectrace/manage.py parse_specs specs/` to import
3. Check Django admin at http://localhost:8000/admin to verify

---

**Last Updated**: 2026-01-20
**Project Status**: Phase 1 (Foundation) - Basic spec parsing and database storage implemented
