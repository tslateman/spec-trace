# SpecTrace

Requirements traceability for Python projects. Connect specs to tests, see what's verified.

## Architecture

Three parts, one direction of flow: the CLI reads and pushes, the Worker
stores and serves, humans and agents read.

- **`spectrace` CLI (Python)** — the only reader of specs, tests, and git. It
  parses `specs/`, runs analyzers, and pushes results to the Worker.
- **Worker** (`worker/`) — the v1 API, D1 storage, and one public demo page
  at `/demo/`. Serves production at `spectrace.spectrace.workers.dev`. CI
  deploys it on every merge to `main` and pushes specs, links, flows, and
  JUnit results into it. Its old data-screen URLs now redirect to the
  dashboard.
- **Dashboard** (`app/`) — a React app deployed at
  `spectrace-app.spectrace.workers.dev`, behind GitHub OAuth. It reaches the
  Worker over a service binding, so the request never leaves Cloudflare's
  network.

Every data screen now lives in the dashboard behind GitHub OAuth. The Worker
serves the API, guarded by `SPECTRACE_API_KEY`, redirects its old screen URLs,
and keeps `/demo/` open to anyone. PR #2 deleted the other Hono JSX pages;
`worker/src/screens/` holds only the demo page and the redirects.

The Django server (`spectrace/`) still exists, still runs locally, and is
being retired in favor of the Worker. It has not been stopped. Its management
commands and `just` recipes (`just run`, `just migrate`, `just shell`,
`just makemigrations`) still work — see [plans/cloudflare-port.md](plans/cloudflare-port.md)
for the full migration plan and its status.

## Scope

Code written by agents earns less trust than code you wrote, so trust has to
move to validation. Charity Majors puts it plainly: "we need to increase trust at
the other part of the development process. Specifically, at validation: with
things like tests, evals, and conformance testing." SpecTrace is that part. It
links each requirement to the tests that verify it, checks an agent's work
against the intent it claimed, and reviews each spec against the org's
standards. Human judgment moves from the code to the spec: a rule engine asserts
coverage, and reviewers judge whether a spec honors an obligation.

SpecTrace reads git, specs, and test results. It consumes what your other tools emit,
and never instruments, polls, or scrapes a running system:

- Observability platforms push SLO status in through `update_slo_status --from-json` or
  `POST /api/v1/integrations/slo/status/`. Datadog, groundcover, New Relic — SpecTrace
  needs the mapping from their output to a requirement ID, nothing more.
- Test runners hand over JUnit XML through `spectrace results push`.
- Runtime checks arrive as JSON through the same command, or as
  `POST /api/v1/results/enforcement/`.

Pick your APM. SpecTrace answers a different question: which requirements passing tests
verify, and what a change puts at risk.

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
just install
# or: uv pip install -e .

# Setup database (Django, retiring)
just migrate

# Create admin user (Django, retiring)
just setup

# Import your specs
python spectrace/manage.py parse_specs specs/

# Run development server (Django, retiring)
just run

# Open http://localhost:8000/admin/
```

## Development Commands

SpecTrace uses [`just`](https://github.com/casey/just) as its task runner (itself using `uv`
for package management). Run `just` or `just --list` to list every recipe.

| Command                | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| `just install`         | Install package in editable mode (uses `uv pip install`) |
| `just install-dev`     | Install with dev dependencies, point git at `.githooks`  |
| `just test`            | Run tests with pytest                                    |
| `just lint`            | Lint with ruff                                           |
| `just format`          | Check ruff formatting                                    |
| `just format-fix`      | Rewrite files to ruff's format                           |
| `just check`           | Lint, format, changelog gate, tests                      |
| `just changelog-check` | Fail when a commit is missing from the changelog         |
| `just clean`           | Remove caches and build artifacts                        |
| `just demo`            | Run the SpecTrace demo                                   |

CI runs `just check` plus two jobs it lacks: Verification, which runs
`validate_links --check-high-risk`, and Impact, which posts the code-impact
report on pull requests.

Django recipes — part of the server being retired, still working today:

| Command               | Description                         |
| --------------------- | ----------------------------------- |
| `just migrate`        | Run Django migrations               |
| `just makemigrations` | Create new migrations               |
| `just shell`          | Open Django shell                   |
| `just run`            | Start the Django development server |
| `just setup`          | Create admin user (admin/admin)     |

Worker and dashboard recipes:

| Command                     | Description                                           |
| --------------------------- | ----------------------------------------------------- |
| `just worker-test`          | Run the Worker test suite                             |
| `just worker-typecheck`     | Typecheck the Worker                                  |
| `just worker-lint`          | Lint and format-check the Worker with Biome           |
| `just worker-dev`           | Serve the Worker against local D1                     |
| `just worker-migrate-local` | Apply Worker D1 migrations locally                    |
| `just worker-deploy`        | Deploy the Worker (CI does this on merge to `main`)   |
| `just app-typecheck`        | Typecheck the dashboard                               |
| `just app-lint`             | Lint and format-check the dashboard with Biome        |
| `just app-test`             | Run the dashboard test suite                          |
| `just app-build`            | Build the dashboard                                   |
| `just app-dev`              | Serve the dashboard against the deployed Worker       |
| `just app-dev-local`        | Serve the dashboard and the Worker together, local D1 |
| `just deploy-app`           | Deploy the dashboard by hand (CI deploys on merge)    |
| `just secret-set`           | Store the production key in the login keychain        |
| `just dev-secrets`          | Write the dummy values local development needs        |

**Note:** If you don't have `uv` installed, the Python recipes will fail. Install it first: `pip install uv`

## Workflow Example

```bash
# 1. Import requirements from specs
python spectrace/manage.py parse_specs specs/

# 2. Run tests with JUnit output
just test
# or: pytest --junitxml=test_results.xml

# 3. Extract test-requirement links
python spectrace/manage.py extract_links --output links.json

# 4. Import results and compute status
python spectrace/manage.py import_results test_results.xml --links links.json

# 5. View the Django admin (retiring), or push to the Worker and view spectrace.spectrace.workers.dev
just run
# Open http://localhost:8000/admin/
```

## Examples

One example project per language, each with its own specs, its own suite, and a
CI workflow that pushes its links and results. `.github/workflows/examples.yml`
runs all four.

| Language   | Example                                                    | Runner        |
| ---------- | ---------------------------------------------------------- | ------------- |
| Python     | [document-pipeline](examples/document-pipeline/)           | pytest        |
| TypeScript | [session-api-typescript](examples/session-api-typescript/) | vitest        |
| Go         | [upload-gateway-go](examples/upload-gateway-go/)           | gotestsum     |
| Rust       | [storage-vault-rust](examples/storage-vault-rust/)         | cargo nextest |

The Python example is the deepest: a three-level requirement hierarchy, every
verification method, passing and failing and skipped tests, OpenSLO YAML, and
parametrized, async, class-based, and xfail pytest patterns.

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
verification_method: test # test, inapp, or both
---

Users must be able to log in with email and password.
```

## Linking Tests

A test links to a requirement by naming its ID. Any runner that writes JUnit
XML can link: `spectrace push --links junit.xml` reads the links from the
report and `spectrace results push junit.xml` reads the results, so one file
carries both.

### Python

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

`extract_links` collects the markers into `links.json`.

### TypeScript

Put the ID in brackets in the test name. A tag on a `describe` block links
every test inside it:

```typescript
import { describe, expect, it } from "vitest";

describe("POST /login [REQ-AUTH-001]", () => {
  it("issues a session cookie", async () => {
    // every test in this block verifies REQ-AUTH-001
  });

  it("[REQ-AUTH-002] refuses a locked account", async () => {
    // this test also verifies REQ-AUTH-002
  });
});
```

Write the report with the JUnit reporter in `vitest.config.ts`:

```typescript
test: {
  reporters: ["default", ["junit", { classnameTemplate: "worker/{filename}" }]],
  outputFile: { junit: "junit.xml" },
},
```

The Worker's own suite links this way; see `worker/test/api-tasks.test.ts`.

### Go

Put the ID in brackets in the subtest name:

```go
func TestAccepts(t *testing.T) {
	t.Run("[REQ-AUTH-001] admits a signed token", func(t *testing.T) {
		// this subtest verifies REQ-AUTH-001
	})
}
```

Go replaces the spaces with underscores, so the report carries
`TestAccepts/[REQ-AUTH-001]_admits_a_signed_token`. The tag survives. Tags also
normalize to upper case with hyphens, so a subtest named `[req_auth_001]` names
the same requirement.

`go test` writes no JUnit, so wrap it in `gotestsum`:

```bash
go install gotest.tools/gotestsum@latest
gotestsum --junitfile junit.xml --format testname ./...
```

See `examples/upload-gateway-go/`.

### Rust

Rust names a `#[test]` function with an identifier, and an identifier holds no
brackets. `libtest-mimic` names each trial at run time instead:

```rust
use libtest_mimic::{Arguments, Trial};

fn main() {
    let trials = vec![Trial::test(
        "[REQ-AUTH-001] admits a signed token",
        admits_a_signed_token,
    )];
    libtest_mimic::run(&Arguments::from_args(), trials).exit();
}
```

The target that holds those trials declares its own harness in `Cargo.toml`:

```toml
[dev-dependencies]
libtest-mimic = "0.8"

[[test]]
name = "auth"
harness = false
```

`cargo test` writes no JUnit either. `cargo nextest` does, on stable, from a
profile:

```toml
# .config/nextest.toml
[profile.ci.junit]
path = "junit.xml"
```

```bash
cargo install cargo-nextest --locked
cargo nextest run --profile ci    # writes target/nextest/ci/junit.xml
```

See `examples/storage-vault-rust/`.

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
| `check_invariants`                     | Validate data consistency (ten checks; see the script)      |
| `parse_corpus <dir>`                   | Import corpus entries from markdown into immutable versions |

All commands are run via: `python spectrace/manage.py <command>`

**Agent Task Commands** (see [docs/agent-tasks.md](docs/agent-tasks.md)) call
the Worker's task ledger, not Django, so its spec gate and intent gate hold
for every caller. Run them as `spectrace tasks <command>` with `SPECTRACE_URL`
and `SPECTRACE_API_KEY` set:

| Command           | Description                                               |
| ----------------- | --------------------------------------------------------- |
| `register`        | Register an agent with role (planner/coder/reviewer)      |
| `create`          | Draft a task with requirements, scope, and done_when      |
| `approve-spec`    | Pass the spec-review gate (reviewer)                      |
| `list`            | List tasks by status, a page at a time                    |
| `claim`           | Claim an unclaimed task with lease                        |
| `start`           | Begin work on claimed task                                |
| `validate-intent` | Record an intent evaluation's scores for a commit         |
| `complete`        | Submit work for review; the commit's intent must pass     |
| `review`          | Approve or request changes                                |
| `merge`           | Mark approved task as merged                              |
| `release`         | Return a claimed task to the pool                         |
| `context`         | Assemble the task's context bundle (Django until cutover) |
| `run`             | Drain the unclaimed queue, one worktree per task          |

`tasks run` is the loop the other commands describe, without a person at the
keyboard. One run against a local Worker, with a stand-in scorer:

```
$ spectrace tasks run --agent coder-2 --repo . --coder "$CODER" --tests "$TESTS" --scorer ./score.sh
task-205928-b: working in …/tasks/task-205928-b on task/task-205928-b
task-205928-b: submitted 2c7b401 for review
```

Without `--scorer` the same run stops at the Worker's intent gate:
`task-205928-a: complete refused: INTENT_NOT_VALIDATED`. Details in
[docs/agent-tasks.md](docs/agent-tasks.md#tasks-run).

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
`plans/openapi-worker.yaml` is the contract CI enforces, and
[docs/api-contract.md](docs/api-contract.md) catalogs its v1 operations.

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
  run: just test

- name: Validate requirements coverage
  run: |
    python spectrace/manage.py extract_links --output links.json
    python spectrace/manage.py validate_links links.json --strict
```

### Reporting a run to Linear

`.github/workflows/linear-report.yml` runs `spectrace linear report` once the
Worker workflow finishes on `main`, after that workflow has pushed the run's
results. The reporter comments each requirement's tally on the Linear issue it
came from and sets `tests:passing` or `tests:failing`.

The job needs one secret and two variables, all under **Settings → Secrets and
variables → Actions**:

| Name               | Kind     | Value                                                                                                                                               |
| ------------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LINEAR_API_KEY`   | Secret   | A personal API key from https://linear.app/settings/api — click **Create key**, give it read and write access, and copy the `lin_api_…` string once |
| `LINEAR_WORKSPACE` | Variable | The workspace URL key, the segment after `linear.app/`                                                                                              |
| `LINEAR_TEAM`      | Variable | The team key that prefixes its issue identifiers, `PROJ` in `PROJ-42`                                                                               |

The repository holds no `LINEAR_API_KEY` today, so the job runs, warns that the
secret is unset, and reaches no issue — the same shape the task runner uses for
`CLAUDE_CODE_OAUTH_TOKEN`. Once the key exists, `spectrace linear check` verifies its
shape, identity, and read access before any comment goes out, and a reporter
that cannot post fails the run.

## Project Status

- [ROADMAP.md](ROADMAP.md) — what's next, in priority order
- [CHANGELOG.md](CHANGELOG.md) — milestone history, v1 through today

The changelog's Unreleased section is generated from the commit log:

```bash
just changelog                              # Regenerate before pushing
just changelog-check                        # Fail when it is stale (CI gate)
python scripts/changelog.py release v11     # Promote Unreleased to a version
```

`just install-dev` installs a pre-push hook that runs the check.

## License

MIT
