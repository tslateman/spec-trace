# Agent Guidelines for SpecTrace

This document provides coding guidelines and conventions for AI coding agents working in the SpecTrace repository. SpecTrace is a requirements traceability system connecting product specs (markdown files) to verified code through pytest test annotations, served by a Cloudflare Worker and read by a React dashboard.

## Project Overview

SpecTrace is mid-port from a Django server to Cloudflare Workers. See
`plans/cloudflare-port.md` for the full architecture and phase status. Three
deployables exist today:

- **Worker** (`worker/`) — TypeScript, Hono, Drizzle on D1. Serves the v1 API
  and one public demo page, and redirects its old data-screen URLs to the
  dashboard. Production:
  `spectrace.spectrace.workers.dev`. CI deploys it on every merge to `main`
  (`.github/workflows/worker.yml`).
- **Dashboard** (`app/`) — React, behind GitHub OAuth. Reads the Worker over a
  Cloudflare service binding (`SPECTRACE` in `app/wrangler.jsonc`). Production:
  `spectrace-app.spectrace.workers.dev`. CI deploys it on every merge to
  `main` (`.github/workflows/app.yml`).
- **CLI + Django server** (`spectrace/`) — Python. The CLI (`spectrace push`,
  `spectrace results push`, …) parses specs, tests, and git state and pushes
  them to the Worker; it stays. The Django server that used to serve the same
  data is being retired — do not build on it — but it has **not** been
  stopped yet, so `spectrace/requirements/views.py` and friends still run.

`plans/openapi-worker.yaml` is the frozen v1 API contract.
Any change to Worker request or response shape updates that document and the
Worker tests in `worker/test/` in the same change; `worker/test/contract.test.ts`
fails when the Worker's `/api/v1` operations and the contract's differ.

- **Worker language**: TypeScript, Hono, Drizzle ORM, D1 (SQLite dialect)
- **Dashboard language**: TypeScript, React, Vite
- **CLI/legacy server language**: Python 3.12+ (currently using 3.13), Django 5.2 LTS
- **Database**: D1 (Worker, production), SQLite (Django, being retired)
- **Testing**: Vitest (`worker/test/`) for the Worker; pytest 9.x with pytest-django for the Python side
- **Key Python dependencies**: django-treebeard (hierarchical requirements), python-frontmatter (spec parsing), Markdown

## OpenCode

Plugin setup and session-continuity practices live in
[docs/opencode-workflow.md](docs/opencode-workflow.md).

## Commands

`just` is the task runner. Bare `just` lists every recipe; `just --summary`
prints their names. The justfile lives at the repo root — read it before
assuming a recipe name.

### Python (CLI, Django server)

```bash
# Everything CI runs: lint, format check, changelog gate, tests
just check

# Run all tests (skips demo-marked tests)
just test
# or, for one file or one function
pytest path/to/test_file.py
pytest path/to/test_file.py::test_function_name

# Lint / format
just lint
just format         # check only
just format-fix      # rewrite files

# Start the Django development server (retiring — do not build new features here)
just run

# Django shell
just shell

# Migrations
just migrate
just makemigrations

# Parse spec files into the Django database
python spectrace/manage.py parse_specs specs/
python spectrace/manage.py parse_specs specs/ --clear    # clear existing first
python spectrace/manage.py parse_specs specs/ --dry-run  # validate without saving
```

### Worker (`worker/`)

```bash
just worker-test           # vitest; the run prints the count
just worker-typecheck       # wrangler types && tsc --noEmit
just worker-lint            # biome check: lint, format, import order
just worker-dev              # serve against local D1
just worker-migrate-local    # apply D1 migrations locally
just worker-deploy           # migrate remote D1, then wrangler deploy (CI runs this on merge to main)
```

### Dashboard (`app/`)

```bash
just app-typecheck   # tsc --noEmit
just app-lint        # biome check: lint, format, import order
just app-test        # vitest
just app-build        # vite build
just app-dev           # serve against the deployed Worker (key from the login keychain)
just app-dev-local     # serve the dashboard and the Worker together against local D1
just deploy-app         # vite build, then wrangler deploy; CI does this on merge to main
```

### Pushing

`CHANGELOG.md` carries a generated block. The gate fails when a commit since
the baseline has no entry.

```bash
just push              # regenerate, commit CHANGELOG.md alone, then push
just push origin main  # arguments pass through to git push
just changelog         # regenerate only
just changelog-check   # report staleness
```

Two paths keep the section current:

| Path             | Who writes the commit                 |
| ---------------- | ------------------------------------- |
| `just push`      | you, before the push                  |
| any other client | `github-actions[bot]`, after the push |

The `Changelog` job on `main` regenerates the section, commits it, and pushes.
The pre-push hook reports a stale section and lets the push through. A commit
pushed with `GITHUB_TOKEN` starts no workflow run, so the repair cannot loop.
Pull after pushing from another client — CI adds its commit on top of yours.

Commit `CHANGELOG.md` by itself. A commit touching only `CHANGELOG.md` needs
no entry, so bundling other files makes the gate demand an entry that cannot
exist yet.

### Installation

```bash
# Create the virtualenv and install the package + spectrace-flows (uses uv)
just install

# Install with dev dependencies, and point git at .githooks
just install-dev

# Note: if uv is not installed, install it first:
# curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv
```

### Secrets

Deployed secrets live in Cloudflare (`wrangler secret list`) and in GitHub
Actions. None belong in the repo.

Local development needs no deployed secret. `just dev-secrets` writes
`worker/.dev.vars` with a dummy key, and `just app-dev-local` generates the
rest per run, so `app/.dev.vars` normally does not exist.

`just app-dev` is the exception: its service binding is remote, so the
dashboard presents the production `SPECTRACE_API_KEY` to the deployed Worker.
Store that key once with `just secret-set`, which prompts and writes to the
login keychain. The recipe reads it at startup into a 0600 `app/.dev.vars`
and removes the file when it exits. `just secret-list` reports what the
keychain holds.

`app/.dev.vars.example` documents the GitHub OAuth app setup (two callback
URLs) and the `ALLOWED_LOGINS` allowlist.

### Cleanup

```bash
# Remove caches and build artifacts
just clean
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

- Place tests in a `tests/` directory next to the code being tested (e.g. `spectrace/requirements/tests/`)
- Use pytest conventions: `test_*.py` or `*_test.py` files
- Name test functions with `test_` prefix
- Use descriptive test names that explain what is being tested
- Configure pytest via `pyproject.toml` under `[tool.pytest.ini_options]`
- Use pytest fixtures for shared setup
- Use `@pytest.mark.requirement("REQ-XXX")` to link tests to requirements — already in use across `spectrace/requirements/tests/` and `spectrace/tests/`

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
├── worker/                 # Worker: Hono + Drizzle + D1, the v1 API and /demo/
│   ├── src/api/v1/         # API route handlers (specs, results, tasks, push)
│   ├── src/ledger/         # TaskLedger Durable Object and its state machine
│   ├── src/screens/        # Hono JSX: the public demo page and redirects.ts
│   ├── src/db/schema.ts    # Drizzle schema
│   ├── migrations/         # D1 migrations
│   └── test/                # Vitest suite; `just worker-test` prints the count
├── app/                    # Dashboard: React + Vite, behind GitHub OAuth
│   ├── src/client/          # React app (pages, components)
│   ├── src/server/          # Hono server: OAuth, session, proxy to the Worker
│   └── src/shared/           # Types shared by client and server
├── spectrace/              # CLI (kept) + Django server (retiring, not yet stopped)
│   ├── spectrace_client/    # HTTP client the CLI uses to push to the Worker
│   ├── spectrace/           # Django settings package
│   ├── requirements/        # Django app: models, parser, views, services
│   ├── manage.py            # Django management script
│   └── db.sqlite3           # SQLite database (ignored in git)
├── specs/                  # Spec markdown files
│   ├── example.md          # Example requirement spec
│   └── auth/               # Feature-specific specs
│       ├── login.md
│       └── register.md
├── plans/
│   ├── cloudflare-port.md    # Architecture and phase status for the port
│   └── openapi-worker.yaml   # Frozen v1 API contract (43 operations)
├── .planning/              # Project planning documents (internal use)
├── pyproject.toml          # Python project metadata & dependencies
├── justfile                # Task runner — see Commands above
└── .gitignore              # Git ignore patterns
```

### Where to make a change

- **API behavior or shape** (new field, new endpoint, changed response):
  update `plans/openapi-worker.yaml` first, then `worker/src/api/v1/`, then
  the matching test in `worker/test/`. The contract, the handler, and the
  test move together.
- **A screen** (matrix, coverage, impact, high-risk, requirement detail, …):
  `app/src/client/pages/` in the dashboard. PR #2 deleted the Worker's data
  screens; `worker/src/screens/` keeps only the public demo page and the
  redirects to the dashboard.
- **Task claiming, leases, or the Lore outbox**: `worker/src/ledger/`.
- **Spec parsing, drift detection, or anything the CLI pushes**:
  `spectrace/requirements/parser.py`, `spectrace/requirements/services/`, and
  `spectrace/cli.py`. These stay Python; they do not move to the Worker.
- **Dashboard auth** (GitHub OAuth, session, allowed logins):
  `app/src/server/auth/`.
- **Anything under `spectrace/requirements/views.py`,
  `spectrace/requirements/api.py`, or Django templates**: this is the
  retiring server. Fix a bug there if asked, but build new features on the
  Worker instead.

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
- **Hierarchical storage**: Uses django-treebeard's materialized path for efficient tree queries in the Django server; the Worker keeps the same materialized-path string as a D1 column
- **Parser design**: SpecParser extracts YAML frontmatter + markdown content, handles both single and multi-requirement files
- **Test linking**: pytest markers (`@pytest.mark.requirement("REQ-XXX")`) link tests to requirements
- **Simple state**: Requirement verification status computed from test results, not stored as state machine
- **CLI pushes, Worker serves**: the Worker has no filesystem or subprocess, so it never parses specs or reads git directly. The CLI parses on the machine that holds the checkout and pushes the result over the v1 API. See `plans/cloudflare-port.md` for why.

## Common Tasks

### Adding a New Field to Requirement Model

1. Edit `spectrace/requirements/models.py` to add field
2. Run `just makemigrations` to create migration
3. Run `just migrate` to apply migration
4. Update parser if field should come from spec frontmatter
5. If the field is part of the v1 contract, add it to `plans/openapi-worker.yaml` and to the matching Drizzle column in `worker/src/db/schema.ts`

### Adding a New Management Command

1. Create file in `spectrace/requirements/management/commands/`
2. Inherit from `BaseCommand`
3. Set `help` text and implement `add_arguments` and `handle` methods

### Parsing New Specs

1. Add markdown files to `specs/` directory following format above
2. Run `python spectrace/manage.py parse_specs specs/` to import
3. Check Django admin at http://localhost:8000/admin to verify

---

**Last Updated**: 2026-09-11
**Project Status**: Cloudflare port — phases 0-4 shipped, phase 5 (cutover) in progress. See `plans/cloudflare-port.md`.
