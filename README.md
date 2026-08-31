# SpecTrace

Requirements traceability for Python projects. Connect specs to tests, see what's verified.

## Scope

SpecTrace reads git, specs, and test results. It consumes what your other tools emit,
and never instruments, polls, or scrapes a running system:

- Observability platforms push SLO status in through `update_slo_status --from-json` or
  `POST /api/v1/integrations/slo/status/`. Datadog, groundcover, New Relic — SpecTrace
  needs the mapping from their output to a requirement ID, nothing more.
- Test runners hand over JUnit XML through `import_results`.
- Runtime checks arrive as JSON through `import_inapp_validations`.

Pick your APM. SpecTrace answers a different question: which requirements passing tests
verify, and what a change puts at risk.

A rule engine asserts coverage. Reviewers judge whether a spec honors an obligation.

## Prerequisites

SpecTrace uses [uv](https://github.com/astral-sh/uv) for fast, reliable package management:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv
```

## Quick Start

```bash
# Install with uv (recommended)
make install
# or: uv pip install -e .

# Setup database
make migrate

# Create admin user
make setup

# Import your specs
python spectrace/manage.py parse_specs specs/

# Run development server
make run

# Open http://localhost:8000/admin/
```

## Development Commands

SpecTrace includes a Makefile for common development tasks (uses `uv` for package management):

| Command               | Description                                              |
| --------------------- | -------------------------------------------------------- |
| `make help`           | Show all available commands                              |
| `make install`        | Install package in editable mode (uses `uv pip install`) |
| `make install-dev`    | Install with dev dependencies (uses `uv pip install`)    |
| `make test`           | Run tests with pytest                                    |
| `make migrate`        | Run Django migrations                                    |
| `make makemigrations` | Create new migrations                                    |
| `make shell`          | Open Django shell                                        |
| `make run`            | Start development server                                 |
| `make clean`          | Remove caches and build artifacts                        |
| `make setup`          | Create admin user (admin/admin)                          |
| `make demo`           | Run the SpecTrace demo                                   |

**Note:** If you don't have `uv` installed, the Makefile commands will fail. Install it first: `pip install uv`

## Workflow Example

```bash
# 1. Import requirements from specs
python spectrace/manage.py parse_specs specs/

# 2. Run tests with JUnit output
make test
# or: pytest --junitxml=test_results.xml

# 3. Extract test-requirement links
python spectrace/manage.py extract_links --output links.json

# 4. Import results and compute status
python spectrace/manage.py import_results test_results.xml --links links.json

# 5. View dashboard
make run
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
make demo
# or: python scripts/demo_pipeline.py
```

## Writing Specs

Create markdown files in `specs/` with frontmatter:

```markdown
---
id: REQ-AUTH-001
title: User Login
priority: high
tags: [authentication, security]
verification_method: test # test, inapp, or both
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

## Management Commands

SpecTrace provides Django management commands for various operations:

| Command                                | Description                                                 |
| -------------------------------------- | ----------------------------------------------------------- |
| `parse_specs <dir>`                    | Import requirements from markdown specs into their project  |
| `spec_coverage`                        | Report coverage for one project (`--project`)               |
| `extract_links`                        | Extract test-requirement links from test files              |
| `import_results <xml>`                 | Import pytest JUnit XML and compute status                  |
| `validate_links <json>`                | Validate links for drift detection (CI)                     |
| `import_slos <dir>`                    | Import SLOs from OpenSLO YAML files                         |
| `update_slo_status --from-json <file>` | Update SLO status from observability data                   |
| `import_inapp_validations <json>`      | Import in-app validation results                            |
| `check_invariants`                     | Validate data consistency (INV-A through INV-K)             |
| `parse_corpus <dir>`                   | Import corpus entries from markdown into immutable versions |

**Agent Task Commands** (see [docs/agent-tasks.md](docs/agent-tasks.md)):

| Command          | Description                                          |
| ---------------- | ---------------------------------------------------- |
| `agent_register` | Register an agent with role (planner/coder/reviewer) |
| `agent_tasks`    | List tasks with filtering                            |
| `agent_claim`    | Claim an unclaimed task with lease                   |
| `agent_start`    | Begin work on claimed task                           |
| `agent_submit`   | Submit work for review                               |
| `agent_review`   | Approve or request changes                           |
| `agent_merge`    | Mark approved task as merged                         |
| `expire_leases`  | Release stale task claims (cron)                     |

All commands are run via: `python spectrace/manage.py <command>`

## Corpus Review

The corpus is a git-tracked set of org standards, decisions, and commitments in
`corpus/`, versioned and parsed like specs. A review names every entry a spec
touches, at a pinned corpus version, and records the check as an auditable
artifact.

```bash
# Import the corpus
python spectrace/manage.py parse_corpus corpus/

# Review one spec against it
spectrace corpus review specs/platform/tenant_isolation.md --format md
```

Specs cite entries in frontmatter, with a version on every citation:

```yaml
---
id: REQ-PLAT-001
tags: [platform, security, compliance]
complies_with:
  - STD-SEC-001@4
  - STD-SEC-002@1
---
```

The engine is deterministic. It emits five finding types —
`unaddressed_obligation`, `stale_citation`, `orphan_citation`, `unmet_check`,
`conflicting_obligations` — plus a coverage row for every applicable entry
version, finding or not. Nothing judges whether a spec honors an obligation; the
record proves what was put in front of the reviewer.

| Command                            | Description                                        |
| ---------------------------------- | -------------------------------------------------- |
| `spectrace corpus review <target>` | Review a spec and record coverage plus findings    |
| `spectrace corpus coverage`        | The audit ledger: each requirement's latest review |
| `spectrace corpus drift`           | Reviews the corpus has moved out from under        |
| `spectrace corpus suggest`         | Propose `applies_to` widenings for a human         |

All four take `--format text|json|md`. `corpus review` exits 1 when a finding
carries `enforcement: blocking`; `--strict` escalates advisory findings for one
run. `corpus suggest` always exits 0 — a suggestion is not a finding.

`.claude/skills/spec-review/SKILL.md` drives the tool from a Claude Code agent
and formats the result. It adds no finding the tool did not emit.

Docs:

- [docs/corpus-review.md](docs/corpus-review.md) — one spec end to end, the
  ledger, drift, enforcement
- [docs/corpus-authoring.md](docs/corpus-authoring.md) — frontmatter, scope
  rules, the predicate grammar, versioning

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

Import with: `python spectrace/manage.py import_slos slos/`

## REST API

Every endpoint lives under `/api/v1/`. External systems can push status updates:

| Endpoint                           | Method | Description                                    |
| ---------------------------------- | ------ | ---------------------------------------------- |
| `/api/v1/integrations/slo/status/` | POST   | Update SLO status from observability platforms |
| `/api/v1/results/enforcement/`     | POST   | Submit in-app validation results               |
| `/api/v1/specs/<id>/status/`       | GET    | Get requirement verification status            |

Browse the full surface at `/api/docs/`, or read the spec at `/api/openapi.json`.
[docs/api-contract.md](docs/api-contract.md) catalogs every endpoint.

The unversioned `/api/` paths are retired. They redirect to their `/api/v1/`
successor until 2026-11-28 — see [docs/api-contract.md](docs/api-contract.md) §3.

### Example: Update SLO Status

```bash
curl -X POST http://localhost:8000/api/v1/integrations/slo/status/ \
  -H "Content-Type: application/json" \
  -d '{
    "slos": [
      {"name": "api-availability", "status": "met", "current_value": 0.9995}
    ]
  }'
```

### Example: Submit Validation Result

```bash
curl -X POST http://localhost:8000/api/v1/results/enforcement/ \
  -H "Content-Type: application/json" \
  -d '{
    "source": "production-app",
    "validations": [
      {"requirement_id": "REQ-AUTH-001", "name": "Login Flow", "status": "success"}
    ]
  }'
```

Both POSTs require an API key once `SPECTRACE_API_KEY` is set — add
`-H "X-API-Key: $SPECTRACE_API_KEY"`. A local dev server with the variable unset
accepts the requests above as written.

## CI Integration

Validate test-requirement links in CI to catch drift:

```bash
python spectrace/manage.py validate_links links.json --strict
```

- `--strict` - Exit with error on warnings (missing coverage)
- `--format json` - Output JSON for programmatic parsing

Example in CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: make test

- name: Validate requirements coverage
  run: |
    python spectrace/manage.py extract_links --output links.json
    python spectrace/manage.py validate_links links.json --strict
```

## Project Status

- [ROADMAP.md](ROADMAP.md) — what's next, in priority order
- [CHANGELOG.md](CHANGELOG.md) — milestone history, v1 through today

The changelog's Unreleased section is generated from the commit log:

```bash
make changelog                              # Regenerate before pushing
python scripts/changelog.py check           # Fail when it is stale (CI gate)
python scripts/changelog.py release v11     # Promote Unreleased to a version
```

`make install-dev` installs a pre-push hook that runs the check.

## License

MIT
